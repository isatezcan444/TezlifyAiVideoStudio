import React, { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Loader2, Plus, Youtube } from 'lucide-react';
import { useChannelContext } from '../../context/ChannelContext';

interface ChannelSwitcherProps {
  onManageAccounts: () => void;
}

export const ChannelSwitcher: React.FC<ChannelSwitcherProps> = ({ onManageAccounts }) => {
  const { channels, activeChannel, isLoading, selectChannel } = useChannelContext();
  const [isOpen, setIsOpen] = useState(false);
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = async (channelId: string) => {
    if (channelId === activeChannel?.id) {
      setIsOpen(false);
      return;
    }
    setSwitchingId(channelId);
    try {
      await selectChannel(channelId);
      setIsOpen(false);
    } finally {
      setSwitchingId(null);
    }
  };

  const grouped = channels.reduce<Record<string, typeof channels>>((acc, channel) => {
    const key = channel.account_display_name || 'YouTube Hesabı';
    acc[key] = acc[key] || [];
    acc[key].push(channel);
    return acc;
  }, {});

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-200 dark:hover:bg-white/[0.07]"
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-[#7367F0]" />
        ) : activeChannel?.avatar_url ? (
          <img src={activeChannel.avatar_url} alt="" className="h-5 w-5 rounded-full object-cover" />
        ) : (
          <Youtube className="h-4 w-4 text-red-500" />
        )}
        <span className="hidden max-w-[160px] truncate sm:inline">
          {activeChannel ? activeChannel.channel_name : 'Kanal bağlayın'}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl dark:border-white/[0.08] dark:bg-[#2F3349]">
          <div className="max-h-72 overflow-y-auto p-1.5">
            {Object.keys(grouped).length === 0 ? (
              <div className="px-3 py-4 text-center text-[11px] text-slate-400">
                Yönetilecek kanal yok.
              </div>
            ) : (
              Object.entries(grouped).map(([account, items]) => (
                <div key={account} className="mb-1 last:mb-0">
                  <p className="px-2 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wide text-slate-400">
                    {account}
                  </p>
                  {items.map((channel) => {
                    const isActive = channel.id === activeChannel?.id;
                    return (
                      <button
                        key={channel.id}
                        type="button"
                        onClick={() => handleSelect(channel.id)}
                        className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs transition ${
                          isActive
                            ? 'bg-[#7367F0]/10 text-[#7367F0] dark:bg-[#7367F0]/20 dark:text-[#A59DF8]'
                            : 'text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.05]'
                        }`}
                      >
                        {channel.avatar_url ? (
                          <img src={channel.avatar_url} alt="" className="h-6 w-6 rounded-full object-cover" />
                        ) : (
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold dark:bg-white/10">
                            {channel.channel_name.charAt(0).toUpperCase()}
                          </span>
                        )}
                        <span className="min-w-0 flex-1 truncate">{channel.channel_name}</span>
                        {switchingId === channel.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : isActive ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onManageAccounts();
            }}
            className="flex w-full items-center gap-2 border-t border-slate-100 px-3 py-2.5 text-[11px] font-bold text-[#7367F0] hover:bg-slate-50 dark:border-white/[0.06] dark:hover:bg-white/[0.05]"
          >
            <Plus className="h-3.5 w-3.5" /> Hesap / Kanal Ekle
          </button>
        </div>
      )}
    </div>
  );
};
