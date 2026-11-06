import React from 'react';
import { Sun, Moon, Menu, UploadCloud } from 'lucide-react';
import { Button } from '../ui/button';
import { ChannelSwitcher } from '../channels/ChannelSwitcher';

interface TopHeaderProps {
  title: string;
  subtitle?: string;
  isDark: boolean;
  onToggleTheme: () => void;
  onToggleMobileMenu: () => void;
  onQuickUpload?: () => void;
  onManageAccounts: () => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  title,
  subtitle,
  isDark,
  onToggleTheme,
  onToggleMobileMenu,
  onQuickUpload,
  onManageAccounts,
}) => {
  return (
    <header className="sticky top-0 z-30 px-3 sm:px-6 lg:px-8 pt-3 sm:pt-4 pb-2 select-none">
      <div className="min-h-16 px-2.5 sm:px-6 py-2 sm:py-0 rounded-xl bg-white/95 dark:bg-[#2F3349]/95 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-xs flex items-center justify-between transition-colors duration-200 gap-2 sm:gap-4">
        {/* Left Side: Mobile Menu Button & Page Title */}
        <div className="flex min-w-0 flex-1 items-center space-x-2 sm:space-x-3">
          <button
            type="button"
            onClick={onToggleMobileMenu}
            aria-label="Menüyü aç"
            className="lg:hidden shrink-0 p-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors"
          >
            <Menu className="w-5 h-5" aria-hidden="true" />
          </button>

          <div className="min-w-0">
            <h1 className="line-clamp-2 text-sm sm:text-lg font-extrabold text-slate-800 dark:text-white tracking-tight leading-tight sm:line-clamp-1">
              {title}
            </h1>
            {subtitle && (
              <p className="text-xs text-slate-400 dark:text-[#7E7F96] font-medium hidden sm:block truncate">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Right Side: Channel selector & Quick Actions */}
        <div className="flex items-center space-x-2 sm:space-x-3 shrink-0">
          <ChannelSwitcher onManageAccounts={onManageAccounts} />

          {onQuickUpload && (
            <Button
              variant="default"
              size="sm"
              onClick={onQuickUpload}
              className="hidden gap-1.5 sm:flex"
              aria-label="Video yükle"
            >
              <UploadCloud className="w-4 h-4" />
              <span className="hidden sm:inline">Video Yükle</span>
            </Button>
          )}

          {/* Theme Switcher Button */}
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={isDark ? 'Açık moda geç' : 'Koyu moda geç'}
            aria-pressed={isDark}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors"
            title={isDark ? 'Açık Mod' : 'Koyu Mod'}
          >
            {isDark ? (
              <Sun className="w-5 h-5 text-[#FF9F43]" aria-hidden="true" />
            ) : (
              <Moon className="w-5 h-5 text-[#7367F0]" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};

