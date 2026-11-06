import React, { useState } from 'react';
import { ScheduledPublish, ScheduleStatus } from '../../types/schedule';
import { ScheduleStatusBadge } from './ScheduleStatusBadge';
import { Search, Calendar, RefreshCw, XCircle, Edit2, AlertCircle, Clock } from 'lucide-react';

interface PublishListViewProps {
  schedules: ScheduledPublish[];
  isLoading: boolean;
  onEdit: (schedule: ScheduledPublish) => void;
  onCancel: (schedule: ScheduledPublish) => void;
  onRetry: (schedule: ScheduledPublish) => void;
}

const TABS: { id: string; label: string; status?: ScheduleStatus }[] = [
  { id: 'all', label: 'Tümü' },
  { id: 'scheduled', label: 'Planlandı', status: 'scheduled' },
  { id: 'processing', label: 'İşleniyor', status: 'processing' },
  { id: 'published', label: 'Yayınlandı', status: 'published' },
  { id: 'failed', label: 'Başarısız', status: 'failed' },
  { id: 'missed', label: 'Kaçırıldı', status: 'missed' },
  { id: 'cancelled', label: 'İptal', status: 'cancelled' },
];

export const PublishListView: React.FC<PublishListViewProps> = ({
  schedules,
  isLoading: _isLoading,
  onEdit,
  onCancel,
  onRetry,
}) => {
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const currentTabDef = TABS.find((t) => t.id === activeTab);

  const filtered = schedules.filter((item) => {
    // Filter by status tab
    if (currentTabDef?.status && item.status !== currentTabDef.status) {
      return false;
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchDesc = item.description?.toLowerCase().includes(q);
      const matchId = item.id.toLowerCase().includes(q);
      if (!matchTitle && !matchDesc && !matchId) return false;
    }

    return true;
  });

  const formatScheduledTime = (utcIso: string, _tz?: string) => {
    try {
      const d = new Date(utcIso);
      return {
        dateStr: d.toLocaleDateString('tr-TR', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        }),
        timeStr: d.toLocaleTimeString('tr-TR', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        fullStr: d.toLocaleString('tr-TR'),
      };
    } catch {
      return { dateStr: utcIso, timeStr: '', fullStr: utcIso };
    }
  };

  return (
    <div className="bg-white dark:bg-[#2F3349] rounded-2xl border border-slate-200/80 dark:border-white/[0.08] shadow-sm overflow-hidden transition-colors">
      {/* Controls: Search and Tabs */}
      <div className="p-4 border-b border-slate-100 dark:border-white/[0.08] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          {TABS.map((tab) => {
            const count =
              tab.id === 'all'
                ? schedules.length
                : schedules.filter((s) => s.status === tab.status).length;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1.5 ${
                  activeTab === tab.id
                    ? 'bg-[#7367F0] text-white shadow-sm shadow-[#7367F0]/30'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/[0.05]'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                    activeTab === tab.id
                      ? 'bg-white/20 text-white'
                      : 'bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[220px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Başlık veya id ile ara..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-[#7367F0]/30 transition-colors"
          />
        </div>
      </div>

      {/* Mobile cards */}
      <div className="divide-y divide-slate-100 dark:divide-white/[0.06] sm:hidden">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
            <Calendar className="mb-2 h-9 w-9 stroke-[1.5] text-slate-300 dark:text-slate-600" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Kayıt Bulunamadı</p>
            <p className="mt-0.5 text-xs text-slate-400">
              {searchQuery
                ? 'Arama kriterine uygun yayın planı yok.'
                : 'Bu kategoride henüz planlanmış bir YouTube yayını yok.'}
            </p>
          </div>
        ) : (
          filtered.map((item) => {
            const timeInfo = formatScheduledTime(item.scheduled_at_utc, item.timezone);
            const canEdit = item.status === 'scheduled' || item.status === 'paused';
            const canCancel = item.status === 'scheduled' || item.status === 'paused';
            const canRetry = item.status === 'failed' || item.status === 'missed';
            return (
              <div key={item.id} className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 min-w-0 text-xs font-semibold text-slate-800 dark:text-slate-100">
                    {item.title}
                  </p>
                  <ScheduleStatusBadge status={item.status} />
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3 text-indigo-500" />
                    {timeInfo.dateStr} · {timeInfo.timeStr}
                  </span>
                  <span className="capitalize">{item.privacy_status}</span>
                  <span>
                    {item.attempt_count}/{item.max_attempts} deneme
                  </span>
                </div>
                {item.last_error_message && (
                  <p className="line-clamp-2 text-[11px] text-red-500">{item.last_error_message}</p>
                )}
                <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => onEdit(item)}
                      className="inline-flex min-h-[34px] items-center gap-1 rounded-lg px-2.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/[0.05]"
                    >
                      <Edit2 className="h-3.5 w-3.5" /> Düzenle
                    </button>
                  )}
                  {canRetry && (
                    <button
                      type="button"
                      onClick={() => onRetry(item)}
                      className="inline-flex min-h-[34px] items-center gap-1 rounded-lg px-2.5 text-[11px] font-semibold text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10"
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Yeniden Dene
                    </button>
                  )}
                  {canCancel && (
                    <button
                      type="button"
                      onClick={() => onCancel(item)}
                      className="inline-flex min-h-[34px] items-center gap-1 rounded-lg px-2.5 text-[11px] font-semibold text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
                    >
                      <XCircle className="h-3.5 w-3.5" /> İptal
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Table (tablet and up) */}
      <div className="hidden overflow-x-auto sm:block" role="region" aria-label="Planlanan yayınlar" tabIndex={0}>
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50/70 dark:bg-white/[0.02] text-slate-400 font-semibold border-b border-slate-100 dark:border-white/[0.06] uppercase tracking-wider text-[11px]">
            <tr>
              <th className="py-3 px-4">Yayın & Başlık</th>
              <th className="py-3 px-4">Planlanan Zaman</th>
              <th className="py-3 px-4">Durum</th>
              <th className="py-3 px-4">Deneme</th>
              <th className="py-3 px-4">Gizlilik</th>
              <th className="py-3 px-4 text-right">İşlemler</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/[0.06]">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-400">
                  <div className="flex flex-col items-center justify-center">
                    <Calendar className="w-10 h-10 text-slate-300 dark:text-slate-600 mb-2 stroke-[1.5]" />
                    <p className="font-medium text-sm text-slate-600 dark:text-slate-400">
                      Kayıt Bulunamadı
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {searchQuery
                        ? 'Arama kriterine uygun yayın planı yok.'
                        : 'Bu kategoride henüz planlanmış bir YouTube yayını yok.'}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((item) => {
                const timeInfo = formatScheduledTime(item.scheduled_at_utc, item.timezone);
                const canEdit = item.status === 'scheduled' || item.status === 'paused';
                const canCancel = item.status === 'scheduled' || item.status === 'paused';
                const canRetry = item.status === 'failed' || item.status === 'missed';

                return (
                  <tr
                    key={item.id}
                    className="hover:bg-slate-50/50 dark:hover:bg-white/[0.02] transition-colors"
                  >
                    {/* Title & Info */}
                    <td className="py-3.5 px-4 max-w-xs">
                      <div className="font-semibold text-slate-800 dark:text-slate-100 line-clamp-1">
                        {item.title}
                      </div>
                      <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                        <span className="uppercase text-[#7367F0] font-medium">{item.platform}</span>
                        <span>•</span>
                        <span className="truncate max-w-[150px]">ID: {item.id.slice(0, 12)}...</span>
                      </div>
                      {item.last_error_message && (
                        <div className="text-[11px] text-red-500 mt-1 flex items-center gap-1 line-clamp-1">
                          <AlertCircle className="w-3 h-3 shrink-0" />
                          <span>{item.last_error_message}</span>
                        </div>
                      )}
                    </td>

                    {/* Scheduled Time */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-200">
                        <Clock className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                        <span>{timeInfo.dateStr}</span>
                        <span className="text-slate-400">at</span>
                        <span>{timeInfo.timeStr}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {item.timezone}
                      </div>
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <ScheduleStatusBadge status={item.status} />
                    </td>

                    {/* Attempts */}
                    <td className="py-3.5 px-4 whitespace-nowrap text-slate-600 dark:text-slate-300">
                      <span>{item.attempt_count} / {item.max_attempts}</span>
                    </td>

                    {/* Privacy */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span className="capitalize px-2 py-0.5 rounded-md text-[11px] bg-slate-100 dark:bg-white/[0.05] text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-white/[0.08]">
                        {item.privacy_status}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 whitespace-nowrap text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {canEdit && (
                          <button
                            onClick={() => onEdit(item)}
                            title="Planı Düzenle"
                            className="p-1.5 text-slate-500 hover:text-[#7367F0] hover:bg-[#7367F0]/10 rounded-lg transition-colors"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {canRetry && (
                          <button
                            onClick={() => onRetry(item)}
                            title="Tekrar Dene"
                            className="p-1.5 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 rounded-lg transition-colors flex items-center gap-1"
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                            <span className="text-[11px] font-medium hidden sm:inline">Yeniden Dene</span>
                          </button>
                        )}

                        {canCancel && (
                          <button
                            onClick={() => onCancel(item)}
                            title="Planı İptal Et"
                            className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
