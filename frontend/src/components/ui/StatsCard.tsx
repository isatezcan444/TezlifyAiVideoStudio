import React from 'react';
import { Card, CardContent } from './card';
import { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/utils';

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: 'primary' | 'success' | 'warning' | 'info';
  className?: string;
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'primary',
  className,
}) => {
  const variantStyles = {
    primary: {
      bg: 'bg-[#7367F0]/10 text-[#7367F0]',
      shadow: 'hover:shadow-[#7367F0]/20',
    },
    success: {
      bg: 'bg-[#28C76F]/10 text-[#28C76F]',
      shadow: 'hover:shadow-[#28C76F]/20',
    },
    warning: {
      bg: 'bg-[#FF9F43]/10 text-[#FF9F43]',
      shadow: 'hover:shadow-[#FF9F43]/20',
    },
    info: {
      bg: 'bg-[#00CFE8]/10 text-[#00CFE8]',
      shadow: 'hover:shadow-[#00CFE8]/20',
    },
  }[variant];

  return (
    <Card className={cn('overflow-hidden hover:shadow-lg transition-all', variantStyles.shadow, className)}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-semibold text-slate-500 dark:text-[#7E7F96] tracking-wide uppercase">
              {title}
            </p>
            <h3 className="text-2xl font-extrabold text-slate-800 dark:text-white tracking-tight">
              {value}
            </h3>
            {subtitle && (
              <p className="text-xs text-slate-400 dark:text-[#7E7F96]">
                {subtitle}
              </p>
            )}
          </div>
          <div className={cn('p-3 rounded-xl flex items-center justify-center shrink-0', variantStyles.bg)}>
            <Icon className="w-6 h-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
