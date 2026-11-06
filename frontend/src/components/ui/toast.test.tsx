import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider, useToast, type ToastOptions } from './toast';

function Harness({ options }: { options: ToastOptions }) {
  const { notify } = useToast();
  return <button onClick={() => notify(options)}>Göster</button>;
}

function renderToast(options: ToastOptions) {
  render(
    <ToastProvider>
      <Harness options={options} />
    </ToastProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Göster' }));
}

describe('ToastProvider', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the title and description of a notification', () => {
    renderToast({
      title: 'Plan güncellendi',
      description: 'Yayın saati kaydedildi.',
      variant: 'success',
    });

    expect(screen.getByRole('status')).toHaveTextContent('Plan güncellendi');
    expect(screen.getByText('Yayın saati kaydedildi.')).toBeInTheDocument();
  });

  it('uses the alert role for errors', () => {
    renderToast({ title: 'İptal edilemedi', variant: 'error' });

    expect(screen.getByRole('alert')).toHaveTextContent('İptal edilemedi');
  });

  it('dismisses itself after the default duration', () => {
    vi.useFakeTimers();
    renderToast({ title: 'Kaydedildi', variant: 'info' });

    expect(screen.getByRole('status')).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('can be dismissed with the close button', () => {
    renderToast({ title: 'Silindi', variant: 'success' });

    fireEvent.click(screen.getByLabelText('Bildirimi kapat'));

    expect(screen.queryByRole('status')).toBeNull();
  });
});
