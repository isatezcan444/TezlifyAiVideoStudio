import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Modal } from './Modal';

function renderModal(isOpen: boolean, onClose = vi.fn()) {
  return render(
    <Modal isOpen={isOpen} onClose={onClose} title="Test Modalı">
      <button type="button">Birinci</button>
      <button type="button">İkinci</button>
    </Modal>,
  );
}

describe('Modal accessibility', () => {
  beforeEach(() => {
    document.body.style.overflow = '';
    delete document.body.dataset.modalOpen;
  });

  it('exposes a labelled modal dialog and focuses its first control', () => {
    renderModal(true);

    const dialog = screen.getByRole('dialog', { name: 'Test Modalı' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByLabelText('Kapat')).toHaveFocus();
  });

  it('traps keyboard focus inside the dialog', () => {
    renderModal(true);

    const close = screen.getByLabelText('Kapat');
    const last = screen.getByRole('button', { name: 'İkinci' });

    last.focus();
    fireEvent.keyDown(window, { key: 'Tab' });
    expect(close).toHaveFocus();

    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
    expect(last).toHaveFocus();
  });

  it('locks background scroll while open and releases it on close', () => {
    const { rerender } = renderModal(true);

    expect(document.body.dataset.modalOpen).toBe('true');
    expect(document.body.style.overflow).toBe('hidden');

    rerender(
      <Modal isOpen={false} onClose={vi.fn()} title="Test Modalı">
        <button type="button">Birinci</button>
      </Modal>,
    );

    expect(document.body.dataset.modalOpen).toBeUndefined();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('closes on escape and restores the previous focus', () => {
    const onClose = vi.fn();
    const opener = document.createElement('button');
    opener.textContent = 'Aç';
    document.body.appendChild(opener);
    opener.focus();

    const { rerender } = renderModal(false, onClose);
    rerender(
      <Modal isOpen onClose={onClose} title="Test Modalı">
        <button type="button">Birinci</button>
      </Modal>,
    );
    expect(screen.getByLabelText('Kapat')).toHaveFocus();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(
      <Modal isOpen={false} onClose={onClose} title="Test Modalı">
        <button type="button">Birinci</button>
      </Modal>,
    );
    expect(opener).toHaveFocus();

    opener.remove();
  });
});
