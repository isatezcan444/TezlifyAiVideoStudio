import React from 'react';
import { Badge } from './badge';
import { CheckCircle2, Clock, AlertCircle, RefreshCw } from 'lucide-react';

export type MediaStatus = 'ready' | 'processing' | 'failed' | 'pending';

interface StatusBadgeProps {
  status: MediaStatus | string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  switch (status.toLowerCase()) {
    case 'ready':
      return (
        <Badge variant="success" className={className}>
          <CheckCircle2 className="w-3 h-3 mr-1" />
          Hazır
        </Badge>
      );
    case 'processing':
      return (
        <Badge variant="info" className={className}>
          <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
          İşleniyor
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="destructive" className={className}>
          <AlertCircle className="w-3 h-3 mr-1" />
          Hata
        </Badge>
      );
    case 'pending':
    default:
      return (
        <Badge variant="warning" className={className}>
          <Clock className="w-3 h-3 mr-1" />
          Beklemede
        </Badge>
      );
  }
};

