import React from 'react';
import {
  LayoutDashboard,
  Film,
  UploadCloud,
  Settings,
  Sparkles,
  Radio,
  X,
  Server,
  Youtube,
  Calendar,
  Clapperboard,
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isBackendConnected: boolean;
  totalVideosCount?: number;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  isBackendConnected,
  totalVideosCount = 0,
  isOpenMobile = false,
  onCloseMobile = () => {},
}) => {
  const sections = [
    {
      title: 'AI STUDIO',
      items: [
        {
          id: 'studio',
          label: 'AI Video Studio',
          icon: LayoutDashboard,
          badge: '4.6',
          badgeColor: 'bg-[#7367F0]/15 text-[#7367F0] dark:bg-[#7367F0]/25 dark:text-[#A59DF8]',
        },
        {
          id: 'media-library',
          label: 'Medya Kütüphanesi',
          icon: Film,
          badge: totalVideosCount > 0 ? `${totalVideosCount}` : null,
          badgeColor: 'bg-[#7367F0]/15 text-[#7367F0] dark:bg-[#7367F0]/25 dark:text-[#A59DF8]',
        },
        {
          id: 'import-video',
          label: 'Video İçe Aktar',
          icon: UploadCloud,
          badge: null,
        },
      ],
    },
    {
      title: 'YAYIN',
      items: [
        {
          id: 'youtube-publisher',
          label: 'YouTube Publisher',
          icon: Youtube,
          badge: null,
        },
        {
          id: 'scheduler',
          label: 'Yayın Takvimi',
          icon: Calendar,
          badge: null,
        },
      ],
    },
    {
      title: 'GELİŞMİŞ ARAÇLAR',
      items: [
        {
          id: 'character-studio',
          label: 'Karakter & Animasyon',
          icon: Sparkles,
          badge: '4.3',
          badgeColor: 'bg-emerald-500/15 text-emerald-600 dark:bg-emerald-500/25 dark:text-emerald-400',
        },
        {
          id: 'composition-studio',
          label: 'Video Kompozisyon',
          icon: Clapperboard,
          badge: '4.5',
          badgeColor: 'bg-purple-500/15 text-purple-600 dark:bg-purple-500/25 dark:text-purple-400',
        },
        {
          id: 'settings',
          label: 'Sistem Durumu',
          icon: Settings,
          badge: null,
        },
      ],
    },
  ];

  const handleTabClick = (tabId: string) => {
    setActiveTab(tabId);
    onCloseMobile();
  };

  const sidebarContent = (
    <aside className="w-64 h-screen bg-white dark:bg-[#2F3349] border-r border-slate-200/80 dark:border-white/[0.08] flex flex-col transition-colors duration-200 select-none z-40">
      {/* Brand Header */}
      <div className="h-16 px-6 flex items-center justify-between border-b border-slate-100 dark:border-white/[0.08] shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#7367F0] to-[#9E95F5] text-white flex items-center justify-center shadow-md shadow-[#7367F0]/30">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-extrabold text-base tracking-tight text-slate-800 dark:text-white">
                Tezlify
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#7367F0]/15 text-[#7367F0] dark:bg-[#7367F0]/25 dark:text-[#A59DF8]">
                STUDIO
              </span>
            </div>
            <p className="text-[10px] text-slate-400 dark:text-[#7E7F96] font-medium">
              AI Video & 2.5D Engine
            </p>
          </div>
        </div>

        {/* Mobile Close Button */}
        <button
          onClick={onCloseMobile}
          className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05]"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Backend Engine Status Pill */}
      <div className="px-4 py-2.5 mx-3 my-3 rounded-lg bg-slate-50 dark:bg-white/[0.03] border border-slate-200/60 dark:border-white/[0.05] flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-2 truncate">
          <span
            className={`w-2.5 h-2.5 rounded-full shrink-0 ${
              isBackendConnected ? 'bg-[#28C76F] shadow-xs shadow-[#28C76F]' : 'bg-[#EA5455]'
            }`}
          />
          <span className="text-xs font-bold text-slate-600 dark:text-slate-300 truncate">
            {isBackendConnected ? 'Yerel Motor Aktif' : 'Motor Bağlantısı Yok'}
          </span>
        </div>
        <Radio
          className={`w-3.5 h-3.5 shrink-0 ${
            isBackendConnected ? 'text-[#28C76F]' : 'text-slate-400'
          }`}
        />
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 space-y-4 overflow-y-auto pt-1">
        {sections.map((section, sIdx) => (
          <div key={sIdx} className="space-y-1">
            <div className="px-3 py-1 text-[10px] font-extrabold text-slate-400 dark:text-[#7E7F96] uppercase tracking-wider">
              {section.title}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleTabClick(item.id)}
                  className={`w-full min-h-[42px] flex items-center justify-between px-3.5 py-2 rounded-xl text-xs font-semibold transition-all duration-150 cursor-pointer ${
                    isActive
                      ? 'bg-gradient-to-r from-[#7367F0] to-[#867BFF] text-white shadow-md shadow-[#7367F0]/40 font-bold'
                      : 'text-slate-600 dark:text-[#DBD7EC] hover:bg-slate-100 dark:hover:bg-white/[0.04] hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-3 truncate">
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                        isActive
                          ? 'bg-white/20 text-white'
                          : item.badgeColor || 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-100 dark:border-white/[0.08] text-center">
        <div className="flex items-center justify-center space-x-1.5 text-[11px] text-slate-400 dark:text-[#7E7F96]">
          <Server className="w-3.5 h-3.5" />
          <span>v1.0.0 · Local-First Core</span>
        </div>
      </div>
    </aside>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <div className="hidden lg:block shrink-0">{sidebarContent}</div>

      {/* Mobile Drawer */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
          />
          <div className="fixed inset-y-0 left-0 w-64 shadow-2xl">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};

