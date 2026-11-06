import React, { useState } from 'react';
import { ScheduledPublish } from '../../types/schedule';
import { ChevronLeft, ChevronRight, Clock, Plus } from 'lucide-react';
import { Button } from '../ui/button';

interface PublishCalendarViewProps {
  schedules: ScheduledPublish[];
  onSelectSchedule: (schedule: ScheduledPublish) => void;
  onNewScheduleOnDate: (date: Date) => void;
}

export const PublishCalendarView: React.FC<PublishCalendarViewProps> = ({
  schedules,
  onSelectSchedule,
  onNewScheduleOnDate,
}) => {
  const [currentDate, setCurrentDate] = useState(() => new Date());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  // Month name in Turkish
  const monthName = currentDate.toLocaleString('tr-TR', { month: 'long', year: 'numeric' });

  // Get first day of month (0 = Sunday, 1 = Monday)
  const firstDay = new Date(year, month, 1);
  const startingDay = (firstDay.getDay() + 6) % 7; // Monday = 0
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  // Create calendar cells (42 cells: 6 rows of 7 days)
  const calendarCells: { date: Date; isCurrentMonth: boolean; isToday: boolean }[] = [];

  // Previous month overflow days
  for (let i = startingDay - 1; i >= 0; i--) {
    const d = new Date(year, month - 1, daysInPrevMonth - i);
    calendarCells.push({ date: d, isCurrentMonth: false, isToday: false });
  }

  // Current month days
  const today = new Date();
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d);
    const isToday =
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear();
    calendarCells.push({ date, isCurrentMonth: true, isToday });
  }

  // Next month overflow days
  const remaining = 42 - calendarCells.length;
  for (let d = 1; d <= remaining; d++) {
    const date = new Date(year, month + 1, d);
    calendarCells.push({ date, isCurrentMonth: false, isToday: false });
  }

  // Map schedules to date string YYYY-MM-DD
  const schedulesByDate = new Map<string, ScheduledPublish[]>();
  schedules.forEach((item) => {
    const itemDate = new Date(item.scheduled_at_utc);
    const y = itemDate.getFullYear();
    const m = (itemDate.getMonth() + 1).toString().padStart(2, '0');
    const d = itemDate.getDate().toString().padStart(2, '0');
    const key = `${y}-${m}-${d}`;
    if (!schedulesByDate.has(key)) {
      schedulesByDate.set(key, []);
    }
    schedulesByDate.get(key)!.push(item);
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published':
        return 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30';
      case 'processing':
        return 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30';
      case 'failed':
        return 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30';
      case 'missed':
        return 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30';
      case 'cancelled':
        return 'bg-gray-500/15 text-gray-500 dark:text-gray-400 border-gray-500/30';
      case 'scheduled':
      default:
        return 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30';
    }
  };

  const WEEKDAYS = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];

  return (
    <div className="bg-white dark:bg-[#2F3349] rounded-2xl border border-slate-200/80 dark:border-white/[0.08] shadow-sm overflow-hidden transition-colors">
      {/* Calendar Header Controls */}
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 p-3 dark:border-white/[0.08] sm:p-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <h3 className="truncate text-sm font-semibold capitalize text-slate-800 dark:text-slate-100 sm:text-base">
            {monthName}
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={goToToday}
            className="h-7 shrink-0 px-2.5 text-xs"
          >
            Bugün
          </Button>
        </div>

        <div className="flex shrink-0 items-center space-x-1">
          <button
            type="button"
            onClick={prevMonth}
            aria-label="Önceki ay"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-slate-50 dark:border-white/[0.08] dark:text-slate-300 dark:hover:bg-white/[0.05]"
          >
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={nextMonth}
            aria-label="Sonraki ay"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-slate-50 dark:border-white/[0.08] dark:text-slate-300 dark:hover:bg-white/[0.05]"
          >
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Weekday Labels */}
      <div className="grid grid-cols-7 border-b border-slate-100 dark:border-white/[0.08] bg-slate-50/60 dark:bg-white/[0.02] text-center py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
        {WEEKDAYS.map((wd) => (
          <div key={wd}>{wd}</div>
        ))}
      </div>

      {/* Days Grid */}
      <div className="grid grid-cols-7 auto-rows-[84px] divide-x divide-y divide-slate-100 dark:divide-white/[0.06] sm:auto-rows-[110px]">
        {calendarCells.map((cell, idx) => {
          const y = cell.date.getFullYear();
          const m = (cell.date.getMonth() + 1).toString().padStart(2, '0');
          const d = cell.date.getDate().toString().padStart(2, '0');
          const cellKey = `${y}-${m}-${d}`;
          const itemsOnThisDay = schedulesByDate.get(cellKey) || [];

          return (
            <div
              key={idx}
              className={`p-1.5 flex flex-col justify-between group relative transition-colors ${
                cell.isCurrentMonth
                  ? 'bg-transparent hover:bg-slate-50/70 dark:hover:bg-white/[0.02]'
                  : 'bg-slate-50/40 dark:bg-white/[0.01] text-slate-300 dark:text-slate-600'
              }`}
            >
              {/* Day Number and Quick Add Button */}
              <div className="flex items-center justify-between">
                <span
                  className={`text-xs font-semibold inline-flex items-center justify-center w-6 h-6 rounded-full ${
                    cell.isToday
                      ? 'bg-[#7367F0] text-white shadow-sm shadow-[#7367F0]/40'
                      : cell.isCurrentMonth
                      ? 'text-slate-700 dark:text-slate-200'
                      : 'text-slate-400 dark:text-slate-600'
                  }`}
                >
                  {cell.date.getDate()}
                </span>

                {cell.isCurrentMonth && (
                  <button
                    type="button"
                    onClick={() => onNewScheduleOnDate(cell.date)}
                    title="Bu tarihe yayın planla"
                    aria-label={`${cell.date.getDate()} tarihine yayın planla`}
                    className="rounded-md p-2 text-slate-400 transition-opacity hover:text-[#7367F0] xl:opacity-0 xl:group-hover:opacity-100 xl:focus-visible:opacity-100"
                  >
                    <Plus className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                )}
              </div>

              {/* Items for this day */}
              <div className="flex-1 overflow-y-auto mt-1 space-y-1 scrollbar-none">
                {itemsOnThisDay.map((sched) => {
                  const dObj = new Date(sched.scheduled_at_utc);
                  const time = dObj.toLocaleTimeString('tr-TR', {
                    hour: '2-digit',
                    minute: '2-digit',
                  });

                  return (
                    <button
                      key={sched.id}
                      onClick={() => onSelectSchedule(sched)}
                      className={`w-full text-left px-1.5 py-0.5 rounded text-[11px] font-medium border truncate transition-transform hover:scale-[1.02] flex items-center gap-1 ${getStatusColor(
                        sched.status
                      )}`}
                    >
                      <Clock className="w-2.5 h-2.5 shrink-0" />
                      <span className="font-bold text-[10px]">{time}</span>
                      <span className="truncate">{sched.title}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
