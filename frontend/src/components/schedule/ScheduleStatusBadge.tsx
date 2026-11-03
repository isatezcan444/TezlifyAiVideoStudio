import React from 'react';
import { ScheduleStatus } from '../../types/schedule';
import { Clock, CheckCircle2, AlertCircle, XCircle, PauseCircle, AlertTriangle, RefreshCw } from 'lucide-react';

interface ScheduleStatusBadgeProps {
  status: ScheduleStatus;
  showIcon?: boolean;
}

export const ScheduleStatusBadge: React.FC<ScheduleStatusBadgeProps> = ({ status, showIcon = true }) => {
  switch (status) {
    case 'scheduled':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
          {showIcon && <Clock className="w-3.5 h-3.5" />}
          Planlandı
        </span>
      );
    case 'processing':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
          {showIcon && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
          İşleniyor
        </span>
      );
    case 'published':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
          {showIcon && <CheckCircle2 className="w-3.5 h-3.5" />}
          Yayınlandı
        </span>
      );
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
          {showIcon && <AlertCircle className="w-3.5 h-3.5" />}
          Başarısız
        </span>
      );
    case 'paused':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
          {showIcon && <PauseCircle className="w-3.5 h-3.5" />}
          Duraklatıldı
        </span>
      );
    case 'cancelled':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-500/10 text-gray-600 dark:text-gray-400 border border-gray-500/20">
          {showIcon && <XCircle className="w-3.5 h-3.5" />}
          İptal Edildi
        </span>
      );
    case 'missed':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
          {showIcon && <AlertTriangle className="w-3.5 h-3.5" />}
          Kaçırıldı
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
          {status}
        </span>
      );
  }
};
