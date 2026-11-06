import React, { useState, useEffect, useCallback } from 'react';
import { MediaAsset } from '../types/media';
import { ScheduledPublish, SchedulerStatusResponse } from '../types/schedule';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { SchedulerStatusCard } from '../components/schedule/SchedulerStatusCard';
import { PublishCalendarView } from '../components/schedule/PublishCalendarView';
import { PublishListView } from '../components/schedule/PublishListView';
import { ScheduleModal } from '../components/schedule/ScheduleModal';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/toast';
import { Button } from '../components/ui/button';
import { Calendar, List, Plus, AlertCircle } from 'lucide-react';

interface SchedulerPageProps {
  videos: MediaAsset[];
  initialAssetToSchedule?: MediaAsset | null;
  onClearInitialAsset?: () => void;
}

export const SchedulerPage: React.FC<SchedulerPageProps> = ({
  videos,
  initialAssetToSchedule = null,
  onClearInitialAsset = () => {},
}) => {
  const { activeChannel } = useChannelContext();
  const { notify } = useToast();
  const channelId = activeChannel?.id;
  const [schedules, setSchedules] = useState<ScheduledPublish[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');

  // Modal States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<ScheduledPublish | null>(null);
  const [preselectedAsset, setPreselectedAsset] = useState<MediaAsset | null>(null);

  // Cancellation Confirmation Dialog
  const [scheduleToCancel, setScheduleToCancel] = useState<ScheduledPublish | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Error Banner
  const [pageError, setPageError] = useState<string | null>(null);

  const fetchSchedulerData = useCallback(async () => {
    try {
      setPageError(null);
      const [listRes, statusRes] = await Promise.all([
        apiService.listSchedules(undefined, 100, 0, channelId),
        apiService.getSchedulerStatus(),
      ]);
      setSchedules(listRes.items);
      setSchedulerStatus(statusRes);
    } catch (err: any) {
      console.error('Scheduler verileri yüklenemedi:', err);
      setPageError(err.message || 'Veriler yüklenirken bağlantı hatası oluştu.');
    } finally {
      setIsLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    setSchedules([]);
    fetchSchedulerData();

    // Auto refresh every 15 seconds
    const interval = setInterval(fetchSchedulerData, 15000);
    return () => clearInterval(interval);
  }, [fetchSchedulerData]);

  // If page was navigated with an initial asset to schedule
  useEffect(() => {
    if (initialAssetToSchedule) {
      setPreselectedAsset(initialAssetToSchedule);
      setEditingSchedule(null);
      setIsModalOpen(true);
      onClearInitialAsset();
    }
  }, [initialAssetToSchedule, onClearInitialAsset]);

  const handleCreateNew = () => {
    setEditingSchedule(null);
    setPreselectedAsset(null);
    setIsModalOpen(true);
  };

  const handleEditSchedule = (sched: ScheduledPublish) => {
    setEditingSchedule(sched);
    setPreselectedAsset(null);
    setIsModalOpen(true);
  };

  const handleNewScheduleOnDate = (_date: Date) => {
    setEditingSchedule(null);
    setPreselectedAsset(null);
    setIsModalOpen(true);
  };

  const handleCancelConfirm = async () => {
    if (!scheduleToCancel) return;
    setIsCancelling(true);
    try {
      const updated = await apiService.cancelSchedule(scheduleToCancel.id);
      setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setScheduleToCancel(null);
      fetchSchedulerData();
    } catch (err: any) {
      notify({
        variant: 'error',
        title: 'İptal işlemi başarısız',
        description: err.message || 'Bilinmeyen hata',
      });
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetrySchedule = async (sched: ScheduledPublish) => {
    try {
      setIsLoading(true);
      const updated = await apiService.retrySchedule(sched.id);
      setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      fetchSchedulerData();
    } catch (err: any) {
      notify({
        variant: 'error',
        title: 'Tekrar deneme başarısız',
        description: err.message || 'Bilinmeyen hata',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <span>YouTube Yayın Takvimi</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Videolarınızı ileri bir tarih ve saate planlayın; sistem arka planda güvenle YouTube'a yüklesin.
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-end">
          {/* View Toggle */}
          <div className="bg-slate-200/60 dark:bg-white/[0.06] p-1 rounded-xl flex items-center gap-1">
            <button
              onClick={() => setViewMode('calendar')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                viewMode === 'calendar'
                  ? 'bg-white dark:bg-[#2F3349] text-[#7367F0] shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-800'
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>Takvim</span>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-[#2F3349] text-[#7367F0] shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-800'
              }`}
            >
              <List className="w-3.5 h-3.5" />
              <span>Liste</span>
            </button>
          </div>

          <Button
            onClick={handleCreateNew}
            className="bg-[#7367F0] hover:bg-[#685dd8] text-white flex items-center gap-2 text-xs h-9 shadow-md shadow-[#7367F0]/20"
          >
            <Plus className="w-4 h-4" />
            <span>Yeni Yayın Planla</span>
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-xl border border-[#7367F0]/25 bg-[#7367F0]/5 px-3 py-2 text-[11px] font-semibold text-[#7367F0]">
        <span className="h-1.5 w-1.5 rounded-full bg-[#7367F0]" />
        {activeChannel
          ? `Hedef kanal: ${activeChannel.channel_name}`
          : 'Hedef kanal seçili değil — Bağlı Hesaplar ekranından bir kanal seçin.'}
      </div>

      {pageError && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{pageError}</span>
        </div>
      )}

      {/* Scheduler Background Engine Status Card */}
      <SchedulerStatusCard
        status={schedulerStatus}
        isLoading={isLoading}
        onRefresh={fetchSchedulerData}
      />

      {/* Main View: Calendar or List */}
      {viewMode === 'calendar' ? (
        <PublishCalendarView
          schedules={schedules}
          onSelectSchedule={handleEditSchedule}
          onNewScheduleOnDate={handleNewScheduleOnDate}
        />
      ) : (
        <PublishListView
          schedules={schedules}
          isLoading={isLoading}
          onEdit={handleEditSchedule}
          onCancel={(item) => setScheduleToCancel(item)}
          onRetry={handleRetrySchedule}
        />
      )}

      {/* Schedule Create / Edit Modal */}
      <ScheduleModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingSchedule(null);
          setPreselectedAsset(null);
        }}
        onSuccess={() => {
          fetchSchedulerData();
        }}
        initialAsset={preselectedAsset}
        availableAssets={videos.filter((v) => v.status === 'ready')}
        editingSchedule={editingSchedule}
        channelId={channelId || null}
        channelName={activeChannel?.channel_name || null}
      />

      {/* Cancel Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(scheduleToCancel)}
        onClose={() => setScheduleToCancel(null)}
        onConfirm={handleCancelConfirm}
        title="Planlanmış Yayını İptal Et"
        description={`"${scheduleToCancel?.title}" başlıklı yayının otomatik yüklenmesi iptal edilecektir. İstediğiniz zaman yeniden planlayabilirsiniz.`}
        confirmLabel="Evet, İptal Et"
        cancelLabel="Vazgeç"
        variant="destructive"
        isLoading={isCancelling}
      />
    </div>
  );
};
