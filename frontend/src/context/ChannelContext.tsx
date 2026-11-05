import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiService } from '../services/api';
import {
  ChannelSelection,
  PlatformConnection,
  SwitchableChannel,
} from '../types/account';

const STORAGE_KEY = 'tezlify.active_channel_id';

interface ChannelContextValue {
  connections: PlatformConnection[];
  channels: SwitchableChannel[];
  activeChannel: SwitchableChannel | null;
  selection: ChannelSelection | null;
  isLoading: boolean;
  error: string | null;
  hasChannels: boolean;
  refresh: () => Promise<void>;
  selectChannel: (channelId: string) => Promise<void>;
}

const ChannelContext = createContext<ChannelContextValue | undefined>(undefined);

export const ChannelProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [connections, setConnections] = useState<PlatformConnection[]>([]);
  const [channels, setChannels] = useState<SwitchableChannel[]>([]);
  const [selection, setSelection] = useState<ChannelSelection | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const applySelection = useCallback((next: ChannelSelection) => {
    setSelection(next);
    if (next.active_channel_id) {
      window.localStorage.setItem(STORAGE_KEY, next.active_channel_id);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [connectionsRes, channelsRes] = await Promise.all([
        apiService.listConnections(false),
        apiService.listChannels(),
      ]);
      setConnections(connectionsRes.items);
      setChannels(channelsRes.items);

      let current = channelsRes.selection;
      const cached = window.localStorage.getItem(STORAGE_KEY);

      if (!current.active_channel_id && channelsRes.items.length > 0) {
        const preferred =
          channelsRes.items.find((item) => item.id === cached) || channelsRes.items[0];
        try {
          current = await apiService.selectChannel(preferred.id);
        } catch {
          // Selection will be repaired on the next backend call; keep the list.
        }
      }
      applySelection(current);
    } catch (err: any) {
      setError(err?.message || 'Kanal bilgisi alınamadı.');
      setConnections([]);
      setChannels([]);
      applySelection({ active_channel_id: '', default_platform: 'youtube', updated_at: '' });
    } finally {
      setIsLoading(false);
    }
  }, [applySelection]);

  const selectChannel = useCallback(
    async (channelId: string) => {
      const next = await apiService.selectChannel(channelId);
      applySelection(next);
    },
    [applySelection]
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const activeChannel = useMemo(
    () => channels.find((item) => item.id === selection?.active_channel_id) || null,
    [channels, selection]
  );

  const value = useMemo(
    () => ({
      connections,
      channels,
      activeChannel,
      selection,
      isLoading,
      error,
      hasChannels: channels.length > 0,
      refresh,
      selectChannel,
    }),
    [connections, channels, activeChannel, selection, isLoading, error, refresh, selectChannel]
  );

  return <ChannelContext.Provider value={value}>{children}</ChannelContext.Provider>;
};

export function useChannelContext(): ChannelContextValue {
  const context = useContext(ChannelContext);
  if (!context) {
    throw new Error('useChannelContext must be used inside ChannelProvider');
  }
  return context;
}
