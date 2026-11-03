import React from 'react';
import { cn } from '../../lib/utils';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className }) => {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-8 h-8 border-3',
  }[size];

  return (
    <div
      className={cn(
        'rounded-full animate-spin border-[#7367F0] border-t-transparent',
        sizeClasses,
        className
      )}
      role="status"
    >
      <span className="sr-only">Yükleniyor...</span>
    </div>
  );
};

