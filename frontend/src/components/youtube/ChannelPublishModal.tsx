import React from 'react';
import { MediaAsset } from '../../types/media';
import { PublishRecord } from '../../types/publish';
import { useChannelContext } from '../../context/ChannelContext';
import { YouTubePublishModal } from './YouTubePublishModal';

interface ChannelPublishModalProps {
  asset: MediaAsset | null;
  isOpen: boolean;
  onClose: () => void;
  onPublishStarted: (record: PublishRecord) => void;
}

export const ChannelPublishModal: React.FC<ChannelPublishModalProps> = ({
  asset,
  isOpen,
  onClose,
  onPublishStarted,
}) => {
  const { activeChannel } = useChannelContext();
  return (
    <YouTubePublishModal
      asset={asset}
      isOpen={isOpen}
      onClose={onClose}
      onPublishStarted={onPublishStarted}
      channelId={activeChannel?.id ?? null}
      channelName={activeChannel?.channel_name ?? null}
    />
  );
};
