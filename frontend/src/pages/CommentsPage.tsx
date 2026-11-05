import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2, MessageSquare, RefreshCw, Send, ShieldCheck, ThumbsUp } from 'lucide-react';
import { apiService } from '../services/api';
import { ChannelVideo, VideoComment } from '../types/creator';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDate, formatNumber } from '../lib/utils';

export const CommentsPage: React.FC = () => {
  const [videos, setVideos] = useState<ChannelVideo[]>([]);
  const [videoId, setVideoId] = useState('');
  const [comments, setComments] = useState<VideoComment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyTarget, setReplyTarget] = useState<string | null>(null);
  const [replyText, setReplyText] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  const loadComments = async (selectedVideoId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiService.listComments({ videoId: selectedVideoId || undefined, maxResults: 50 });
      setComments(res.items);
    } catch (err: any) {
      setError(err.message || 'Yorumlar alınamadı.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    apiService
      .listChannelVideos(50)
      .then((res) => setVideos(res.items))
      .catch(() => setVideos([]));
    loadComments();
  }, []);

  const handleReply = async (commentId: string) => {
    if (!replyText.trim()) return;
    setIsSending(true);
    setActionError(null);
    try {
      await apiService.replyToComment(commentId, replyText.trim());
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
    setActionError(null);
    try {
      await apiService.moderateComment(commentId, status);
      await loadComments(videoId);
    } catch (err: any) {
      setActionError(err.message || 'Yorum durumu değiştirilemedi.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349] sm:flex-row sm:items-center sm:justify-between">
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
      ) : (
        <div className="space-y-3">
          {comments.map((comment) => (
            <Card key={comment.comment_id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-slate-800 dark:text-white">{comment.author}</p>
                    <p className="text-[11px] text-slate-400">
                      {formatDate(comment.published_at)} · {comment.video_id}
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
                      className="gap-1.5 text-[11px]"
                    >
                      <Send className="h-3.5 w-3.5" /> Yanıtla
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleModeration(comment.comment_id, 'heldForReview')}
                      className="gap-1.5 text-[11px]"
                    >
                      <ShieldCheck className="h-3.5 w-3.5" /> İncelemeye al
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleModeration(comment.comment_id, 'rejected')}
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
          ))}
        </div>
      )}
    </div>
  );
};
