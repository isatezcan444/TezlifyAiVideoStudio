import React from 'react';
import { SchedulerStatusResponse } from '../../types/schedule';
import { Clock, CheckCircle2, AlertTriangle, AlertCircle, Activity, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';

interface SchedulerStatusCardProps {
  status: SchedulerStatusResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
}

export const SchedulerStatusCard: React.FC<SchedulerStatusCardProps> = ({
  status,
  isLoading,
  onRefresh,
}) => {
  const isRunning = status?.is_running ?? false;

  return (
    <div className="bg-white dark:bg-[#2F3349] rounded-2xl p-5 border border-slate-200/80 dark:border-white/[0.08] shadow-sm transition-colors mb-6">
      <div className="flex flex-col gap-4 border-b border-slate-100 pb-4 dark:border-white/[0.08] sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start space-x-3">
          <div className="w-10 h-10 shrink-0 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
            <Activity className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 sm:text-base">
                Arka Plan Zamanlayıcı Motoru (Scheduler Service)
              </h3>
              <span
                className={`inline-flex shrink-0 items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  isRunning
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
                  }`}
                />
                {isRunning ? 'Çalışıyor (Aktif)' : 'Durduruldu'}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Her {status?.check_interval_seconds ?? 30} saniyede bir bekleyen ve zamanı gelen yayınları otomatik işler.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          {status?.last_tick_at && (
            <span className="text-xs text-slate-400 dark:text-slate-500 hidden md:inline">
              Son kontrol: {new Date(status.last_tick_at).toLocaleTimeString('tr-TR')}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-xs h-8"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Yenile
          </Button>
        </div>
      </div>

      {/* Metric Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4">
        <div className="bg-slate-50 dark:bg-white/[0.02] p-3 rounded-xl border border-slate-100 dark:border-white/[0.04]">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-xs font-medium">Planlandı</span>
            <Clock className="w-4 h-4 text-indigo-500" />
          </div>
          <p className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {status?.upcoming_count ?? 0}
          </p>
        </div>

        <div className="bg-slate-50 dark:bg-white/[0.02] p-3 rounded-xl border border-slate-100 dark:border-white/[0.04]">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-xs font-medium">Yayınlandı</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {status?.published_count ?? 0}
          </p>
        </div>

        <div className="bg-slate-50 dark:bg-white/[0.02] p-3 rounded-xl border border-slate-100 dark:border-white/[0.04]">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-xs font-medium">Kaçırıldı</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {status?.missed_count ?? 0}
          </p>
        </div>

        <div className="bg-slate-50 dark:bg-white/[0.02] p-3 rounded-xl border border-slate-100 dark:border-white/[0.04]">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-xs font-medium">Başarısız</span>
            <AlertCircle className="w-4 h-4 text-red-500" />
          </div>
          <p className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {status?.failed_count ?? 0}
          </p>
        </div>
      </div>
    </div>
  );
};
