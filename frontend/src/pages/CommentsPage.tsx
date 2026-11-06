import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Loader2,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  ThumbsUp,
  Youtube,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { ChannelVideo, VideoComment } from '../types/creator';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDate, formatNumber } from '../lib/utils';
import { CAPABILITY_META, capabilityAllows, capabilityNeedsScope } from '../lib/capabilities';
import { awaitYouTubeOAuth, openOAuthPopup } from '../lib/youtubeOAuth';

export const CommentsPage: React.FC = () => {
  const { activeChannel, connections, refresh } = useChannelContext();
  const channelId = activeChannel?.id;
  const connection = connections.find((item) => item.id === activeChannel?.platform_connection_id);
  const commentsAllowed = capabilityAllows(connection, 'comments');
  const commentsNeedsScope = capabilityNeedsScope(connection, 'comments');
  const [isGrantingComments, setIsGrantingComments] = useState(false);
  const [grantError, setGrantError] = useState<string | null>(null);
  const [videos, setVideos] = useState<ChannelVideo[]>([]);
  const [videoId, setVideoId] = useState('');
  const [comments, setComments] = useState<VideoComment[]>([]);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'newest' | 'oldest' | 'likes' | 'replies'>('newest');
  const [onlyUnanswered, setOnlyUnanswered] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyTarget, setReplyTarget] = useState<string | null>(null);
  const [replyText, setReplyText] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  const videosById = useMemo(
    () => Object.fromEntries(videos.map((video) => [video.video_id, video])),
    [videos]
  );

  const unansweredCount = comments.filter((comment) => comment.total_reply_count === 0).length;
  const totalLikes = comments.reduce((sum, comment) => sum + comment.like_count, 0);
  const videoCount = new Set(comments.map((comment) => comment.video_id)).size;

  const visibleComments = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr');
    const filtered = comments.filter((comment) => {
      if (onlyUnanswered && comment.total_reply_count > 0) return false;
      if (!needle) return true;
      return `${comment.author} ${comment.text}`
        .toLocaleLowerCase('tr')
        .includes(needle);
    });
    const publishedAt = (comment: VideoComment) =>
      comment.published_at ? Date.parse(comment.published_at) : 0;
    return [...filtered].sort((a, b) => {
      switch (sort) {
        case 'oldest':
          return publishedAt(a) - publishedAt(b);
        case 'likes':
          return b.like_count - a.like_count;
        case 'replies':
          return b.total_reply_count - a.total_reply_count;
        default:
          return publishedAt(b) - publishedAt(a);
      }
    });
  }, [comments, query, sort, onlyUnanswered]);

  const loadComments = async (selectedVideoId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiService.listComments({
        videoId: selectedVideoId || undefined,
        maxResults: 50,
        channelId,
      });
      setComments(res.items);
    } catch (err: any) {
      setError(err.message || 'Yorumlar alınamadı.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setVideoId('');
    setVideos([]);
    setComments([]);
    apiService
      .listChannelVideos(50, undefined, channelId)
      .then((res) => setVideos(res.items))
      .catch(() => setVideos([]));
    loadComments();
  }, [channelId]);

  const handleReply = async (commentId: string) => {
    if (!commentsAllowed) {
      setActionError(
        'Yorum yanıtlamak için yorum yönetimi izni gerekiyor. İzin vermeden hiçbir yazma çağrısı yapılmaz.'
      );
      return;
    }
    if (!replyText.trim()) return;
    setIsSending(true);
    setActionError(null);
    try {
      await apiService.replyToComment(commentId, replyText.trim(), channelId);
      setReplyTarget(null);
      setReplyText('');
      await loadComments(videoId);
    } catch (err: any) {
      setActionError(err.message || 'Yanıt gönderilemedi.');
    } finally {
      setIsSending(false);
    }
  };

  const handleModeration = async (commentId: string, status: string) => {
    if (!commentsAllowed) {
      setActionError(
        'Yorum moderasyonu için yorum yönetimi izni gerekiyor. İzin vermeden hiçbir yazma çağrısı yapılmaz.'
      );
      return;
    }
    setActionError(null);
    try {
      await apiService.moderateComment(commentId, status, channelId);
      await loadComments(videoId);
    } catch (err: any) {
      setActionError(err.message || 'Yorum durumu değiştirilemedi.');
    }
  };

  const handleGrantComments = async () => {
    if (!connection) return;
    setIsGrantingComments(true);
    setGrantError(null);
    try {
      const result = awaitYouTubeOAuth();
      const res = await apiService.grantCapabilities(connection.id, ['comments']);
      openOAuthPopup(res.auth_url, `tezlify_grant_comments_${connection.id}`);
      const success = await result;
      await refresh();
      if (!success)
        setGrantError('Yorum yönetimi izni verilmedi. Mevcut hesap bağlantınız ve okuma izinleri korunuyor.');
    } catch (err: any) {
      setGrantError(err?.message || 'Yorum izni başlatılamadı.');
    } finally {
      setIsGrantingComments(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'Yorum', value: comments.length },
          { label: 'Yanıt bekleyen', value: unansweredCount },
          { label: 'Toplam beğeni', value: totalLikes },
          { label: 'Video', value: videoCount },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349]"
          >
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
              {item.label}
            </p>
            <p className="mt-1 text-xl font-extrabold text-slate-800 dark:text-white">
              {formatNumber(item.value)}
            </p>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={videoId}
              onChange={(e) => {
                setVideoId(e.target.value);
                loadComments(e.target.value);
              }}
              className="vuexy-input max-w-xs rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            >
              <option value="">Tüm kanal yorumları</option>
              {videos.map((video) => (
                <option key={video.video_id} value={video.video_id}>
                  {video.title}
                </option>
              ))}
            </select>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Yazar veya yorum ara"
                className="vuexy-input w-48 rounded-lg border border-slate-200 bg-slate-50 py-2 pl-8 pr-3 text-xs dark:border-white/10 dark:bg-white/[0.03]"
              />
            </div>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
              className="vuexy-input rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
              aria-label="Yorum sıralaması"
            >
              <option value="newest">En yeni</option>
              <option value="oldest">En eski</option>
              <option value="likes">En çok beğenilen</option>
              <option value="replies">En çok yanıtlanan</option>
            </select>
            <label className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-300">
              <input
                type="checkbox"
                checked={onlyUnanswered}
                onChange={(e) => setOnlyUnanswered(e.target.checked)}
                className="rounded border-slate-300"
              />
              Sadece yanıtlanmamış
            </label>
            <span className="text-[11px] text-slate-400">YouTube Data API</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadComments(videoId)}
            disabled={isLoading}
            className="gap-1.5 text-xs"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Yenile
          </Button>
        </div>
      </div>

      {!commentsAllowed && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
            <div className="min-w-0 space-y-1.5">
              <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                Yorum yönetimi izni gerekiyor
              </h3>
              <p className="text-xs leading-relaxed text-amber-800 dark:text-amber-300">
                Yorumları okumaya devam edebilirsiniz; yanıtlama ve moderasyon için ek izin gerekir. İzin
                verilmeden hiçbir yazma çağrısı yapılmaz ve mevcut hesap bağlantınız korunur.
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {commentsNeedsScope && (
                  <Button
                    size="sm"
                    onClick={handleGrantComments}
                    disabled={isGrantingComments || !connection}
                    className="gap-2"
                  >
                    {isGrantingComments ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Youtube className="h-4 w-4" />
                    )}
                    {CAPABILITY_META.comments.grantLabel}
                  </Button>
                )}
                <span className="text-[11px] text-amber-700 dark:text-amber-400">
                  {CAPABILITY_META.comments.label} · {commentsAllowed ? 'active' : 'scope_required'}
                </span>
              </div>
              {grantError && (
                <p className="text-xs font-semibold text-amber-700 dark:text-amber-300">{grantError}</p>
              )}
            </div>
          </div>
        </div>
      )}

      {actionError && (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {actionError}
        </div>
      )}

      {error ? (
        <EmptyState icon={AlertTriangle} title="Yorumlar alınamadı" description={error} />
      ) : isLoading ? (
        <div className="flex items-center justify-center py-24 text-xs text-slate-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Yorumlar yükleniyor...
        </div>
      ) : comments.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="Yorum bulunamadı"
          description="Seçilen kapsamda yorum yok. Kanalınızda yorumlar kapalıysa veya henüz yorum yazılmadıysa bu liste boş görünür."
        />
      ) : visibleComments.length === 0 ? (
        <EmptyState
          icon={Search}
          title="Filtrelere uygun yorum yok"
          description="Arama metnini veya sıralama filtrelerini değiştirerek tekrar deneyin."
        />
      ) : (
        <div className="space-y-3">
          {visibleComments.map((comment) => {
            const video = videosById[comment.video_id];
            return (
            <Card key={comment.comment_id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p
                      data-testid="comment-author"
                      className="text-xs font-bold text-slate-800 dark:text-white"
                    >
                      {comment.author}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {formatDate(comment.published_at)} ·{' '}
                      {comment.video_id ? (
                        <a
                          href={`https://www.youtube.com/watch?v=${comment.video_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:text-[#7367F0] hover:underline"
                        >
                          {video?.title || comment.video_id}
                        </a>
                      ) : (
                        '—'
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <ThumbsUp className="h-3.5 w-3.5" /> {formatNumber(comment.like_count)}
                    </span>
                    {comment.moderation_status && (
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold dark:bg-white/[0.06]">
                        {comment.moderation_status}
                      </span>
                    )}
                  </div>
                </div>
                <p className="whitespace-pre-line text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {comment.text}
                </p>

                {replyTarget === comment.comment_id ? (
                  <div className="space-y-2">
                    <textarea
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      rows={2}
                      placeholder="Yanıtınızı yazın..."
                      className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
                    />
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setReplyTarget(null)} disabled={isSending}>
                        Vazgeç
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleReply(comment.comment_id)}
                        disabled={isSending || !replyText.trim()}
                        className="gap-1.5"
                      >
                        {isSending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                        Gönder
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setReplyTarget(comment.comment_id);
                        setReplyText('');
                      }}
                      disabled={!commentsAllowed}
                      title={!commentsAllowed ? 'Yorum yönetimi izni gerekiyor' : undefined}
                      className="gap-1.5 text-[11px]"
                    >
                      <Send className="h-3.5 w-3.5" /> Yanıtla
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleModeration(comment.comment_id, 'heldForReview')}
                      disabled={!commentsAllowed}
                      title={!commentsAllowed ? 'Yorum yönetimi izni gerekiyor' : undefined}
                      className="gap-1.5 text-[11px]"
                    >
                      <ShieldCheck className="h-3.5 w-3.5" /> İncelemeye al
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleModeration(comment.comment_id, 'rejected')}
                      disabled={!commentsAllowed}
                      title={!commentsAllowed ? 'Yorum yönetimi izni gerekiyor' : undefined}
                      className="gap-1.5 text-[11px] text-[#EA5455]"
                    >
                      Reddet
                    </Button>
                  </div>
                )}
                {comment.total_reply_count > 0 && (
                  <p className="text-[11px] text-slate-400">{comment.total_reply_count} yanıt</p>
                )}
              </CardContent>
            </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
