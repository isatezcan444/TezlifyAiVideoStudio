import type { AnalyticsDelta } from '../types/creator';
import { formatNumber } from './utils';

export const deltaClass = (delta: AnalyticsDelta) =>
  delta.change > 0
    ? 'text-emerald-600 dark:text-emerald-400'
    : delta.change < 0
      ? 'text-rose-600 dark:text-rose-400'
      : 'text-slate-400';

export const deltaLabel = (delta: AnalyticsDelta) => {
  if (delta.percent === null) return 'önceki dönemde veri yok';
  const sign = delta.percent > 0 ? '+' : '';
  return `${sign}${delta.percent.toFixed(1)}% · önceki dönem ${formatNumber(delta.previous)}`;
};
