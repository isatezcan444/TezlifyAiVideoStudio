import React from 'react';
import { Sun, Moon, Menu, UploadCloud } from 'lucide-react';
import { Button } from '../ui/button';

interface TopHeaderProps {
  title: string;
  subtitle?: string;
  isDark: boolean;
  onToggleTheme: () => void;
  onToggleMobileMenu: () => void;
  onQuickUpload?: () => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  title,
  subtitle,
  isDark,
  onToggleTheme,
  onToggleMobileMenu,
  onQuickUpload,
}) => {
  return (
    <header className="sticky top-0 z-30 px-4 sm:px-6 lg:px-8 pt-4 pb-2 select-none">
      <div className="h-16 px-4 sm:px-6 rounded-xl bg-white/95 dark:bg-[#2F3349]/95 backdrop-blur-xl border border-slate-200/80 dark:border-white/[0.08] shadow-xs flex items-center justify-between transition-colors duration-200 gap-4">
        {/* Left Side: Mobile Menu Button & Page Title */}
        <div className="flex items-center space-x-3 truncate">
          <button
            type="button"
            onClick={onToggleMobileMenu}
            className="lg:hidden p-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="truncate">
            <h1 className="text-base sm:text-lg font-extrabold text-slate-800 dark:text-white tracking-tight truncate">
              {title}
            </h1>
            {subtitle && (
              <p className="text-xs text-slate-400 dark:text-[#7E7F96] font-medium hidden sm:block truncate">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Right Side: Quick Actions */}
        <div className="flex items-center space-x-2 sm:space-x-3 shrink-0">
          {onQuickUpload && (
            <Button
              variant="default"
              size="sm"
              onClick={onQuickUpload}
              className="gap-1.5"
            >
              <UploadCloud className="w-4 h-4" />
              <span className="hidden sm:inline">Video Yükle</span>
            </Button>
          )}

          {/* Theme Switcher Button */}
          <button
            onClick={onToggleTheme}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors"
            title={isDark ? 'Açık Mod' : 'Koyu Mod'}
          >
            {isDark ? <Sun className="w-5 h-5 text-[#FF9F43]" /> : <Moon className="w-5 h-5 text-[#7367F0]" />}
          </button>
        </div>
      </div>
    </header>
  );
};

