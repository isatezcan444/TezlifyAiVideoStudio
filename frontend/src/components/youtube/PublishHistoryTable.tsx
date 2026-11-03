import React from 'react';
import { PublishRecord } from '../../types/publish';
import { PublishStatusBadge } from './PublishStatusBadge';
import { Button } from '../ui/button';

interface PublishHistoryTableProps {
  records: PublishRecord[];
  onResume: (record: PublishRecord) => void;
  isLoading?: boolean;
}

export const PublishHistoryTable: React.FC<PublishHistoryTableProps> = ({
  records,
  onResume,
}) => {
  if (records.length === 0) {
    return (
      <div className="text-center py-12 px-4 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 bg-white dark:bg-[#2F3349]/50">
        <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h4 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
          Henüz Yayınlanmış Video Bulunmuyor
        </h4>
        <p className="text-xs text-[#828092] dark:text-[#908DA1] mt-1 max-w-sm mx-auto">
          Medya kütüphanenizdeki videolardan birini seçerek doğrudan YouTube kanalınızda yayınlayabilirsiniz.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-[#2F3349]">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-slate-200/80 dark:border-slate-800 text-[11px] font-semibold text-[#828092] dark:text-[#908DA1] uppercase tracking-wider bg-slate-50/50 dark:bg-[#25293C]/50">
            <th className="py-3 px-4">Video / Başlık</th>
            <th className="py-3 px-4">Gizlilik</th>
            <th className="py-3 px-4">Durum</th>
            <th className="py-3 px-4">İlerleme</th>
            <th className="py-3 px-4">Tarih</th>
            <th className="py-3 px-4 text-right">İşlem</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-xs">
          {records.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
              <td className="py-3 px-4 max-w-xs truncate font-medium text-[#4B465C] dark:text-[#DBD7EC]">
                {r.title}
              </td>
              <td className="py-3 px-4">
                <span className="capitalize px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  {r.privacy_status}
                </span>
              </td>
              <td className="py-3 px-4">
                <PublishStatusBadge status={r.status} />
              </td>
              <td className="py-3 px-4 text-slate-500 dark:text-slate-400 font-mono">
                %{r.progress_percentage}
              </td>
              <td className="py-3 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                {new Date(r.created_at).toLocaleDateString('tr-TR')}
              </td>
              <td className="py-3 px-4 text-right whitespace-nowrap">
                {r.status === 'published' && r.external_video_url ? (
                  <a
                    href={r.external_video_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[#7367F0] hover:underline font-medium"
                  >
                    <span>İzle</span>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                ) : r.status === 'paused' ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onResume(r)}
                    className="text-xs text-[#7367F0] hover:bg-[#7367F0]/10"
                  >
                    Devam Et
                  </Button>
                ) : (
                  <span className="text-slate-400">-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
