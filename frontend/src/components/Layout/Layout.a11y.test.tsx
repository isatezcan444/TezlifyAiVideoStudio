import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';

vi.mock('../channels/ChannelSwitcher', () => ({
  ChannelSwitcher: () => <div data-testid="channel-switcher" />,
}));

describe('Layout accessibility', () => {
  it('marks the active navigation item and labels the navigation', () => {
    render(
      <Sidebar activeTab="analytics" setActiveTab={vi.fn()} isBackendConnected />,
    );

    expect(screen.getByRole('navigation', { name: 'Ana gezinme' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analitik' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('button', { name: 'Videolar' })).not.toHaveAttribute(
      'aria-current',
    );
    expect(screen.getByRole('button', { name: 'Menüyü kapat' })).toBeInTheDocument();
  });

  it('labels the mobile menu and theme toggle buttons', () => {
    const { rerender } = render(
      <TopHeader
        title="Panel"
        isDark={false}
        onToggleTheme={vi.fn()}
        onToggleMobileMenu={vi.fn()}
        onManageAccounts={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Menüyü aç' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Koyu moda geç' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );

    rerender(
      <TopHeader
        title="Panel"
        isDark
        onToggleTheme={vi.fn()}
        onToggleMobileMenu={vi.fn()}
        onManageAccounts={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Açık moda geç' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});
