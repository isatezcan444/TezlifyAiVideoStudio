import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CommentsPage } from './CommentsPage';
import { apiService } from '../services/api';
import type { CapabilityName } from '../lib/capabilities';
import type { CapabilityStatus, PlatformConnection } from '../types/account';

const CAPABILITIES: CapabilityName[] = ['identity', 'channel_read', 'comments'];

function connectionWith(commentsActive: boolean): PlatformConnection {
  const capabilities: CapabilityStatus[] = CAPABILITIES.map((name) => ({
    capability: name,
    status: name === 'comments' && !commentsActive ? 'scope_required' : 'active',
    granted: name !== 'comments' || commentsActive,
    optional: false,
    required_scopes: [],
  }));
  return {
    id: 'conn_1',
    platform: 'youtube',
    account_name: 'Test Hesabı',
    capabilities,
  } as unknown as PlatformConnection;
}

const mockContext = {
  connections: [] as PlatformConnection[],
  channels: [],
  activeChannel: { id: 'ch1', platform_connection_id: 'conn_1' } as any,
  selection: null,
  isLoading: false,
  error: null,
  hasChannels: true,
  refresh: vi.fn(),
  selectChannel: vi.fn(),
};

vi.mock('../context/ChannelContext', () => ({
  useChannelContext: () => mockContext,
}));

vi.mock('../services/api', () => ({
  apiService: {
    listComments: vi.fn(),
    listChannelVideos: vi.fn(),
    replyToComment: vi.fn(),
    moderateComment: vi.fn(),
    grantCapabilities: vi.fn(),
  },
}));

vi.mock('../lib/youtubeOAuth', () => ({
  awaitYouTubeOAuth: vi.fn(),
  openOAuthPopup: vi.fn(),
}));

const api = apiService as unknown as Record<string, ReturnType<typeof vi.fn>>;

const COMMENTS = [
  {
    comment_id: 'c1',
    video_id: 'v1',
    author: 'Ayşe',
    text: 'Harika video',
    like_count: 5,
    published_at: '2026-10-03T10:00:00Z',
    updated_at: null,
    total_reply_count: 0,
  },
  {
    comment_id: 'c2',
    video_id: 'v2',
    author: 'Mehmet',
    text: 'Ses biraz kısık',
    like_count: 1,
    published_at: '2026-10-01T10:00:00Z',
    updated_at: null,
    total_reply_count: 2,
  },
  {
    comment_id: 'c3',
    video_id: 'v1',
    author: 'Zeynep',
    text: 'Devamını bekliyorum',
    like_count: 9,
    published_at: '2026-10-02T10:00:00Z',
    updated_at: null,
    total_reply_count: 0,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockContext.connections = [connectionWith(true)];
  api.listComments.mockResolvedValue({ items: COMMENTS, next_page_token: null, source: 'youtube_data_api' });
  api.listChannelVideos.mockResolvedValue({
    items: [
      { video_id: 'v1', title: 'Bölüm 1', description: '', tags: [], privacy_status: 'public' },
      { video_id: 'v2', title: 'Bölüm 2', description: '', tags: [], privacy_status: 'public' },
    ],
    next_page_token: null,
    source: 'youtube_data_api',
  });
  api.replyToComment.mockResolvedValue({ comment: {}, source: 'youtube_data_api' });
  api.moderateComment.mockResolvedValue({ comment: {}, source: 'youtube_data_api' });
});

function summaryValue(label: string): string {
  const labelNode = screen.getByText(label);
  return labelNode.nextElementSibling?.textContent || '';
}

function authors(): string[] {
  return screen.getAllByTestId('comment-author').map((node) => node.textContent || '');
}

describe('CommentsPage depth', () => {
  it('summarises comments and links each comment to its video title', async () => {
    render(<CommentsPage />);

    await screen.findByText('Ayşe');

    expect(summaryValue('Yorum')).toBe('3');
    expect(summaryValue('Yanıt bekleyen')).toBe('2');
    expect(summaryValue('Toplam beğeni')).toBe('15');
    expect(summaryValue('Video')).toBe('2');

    const partOneLinks = screen.getAllByRole('link', { name: 'Bölüm 1' });
    expect(partOneLinks).toHaveLength(2);
    expect(partOneLinks[0]).toHaveAttribute('href', 'https://www.youtube.com/watch?v=v1');
    expect(screen.getByRole('link', { name: 'Bölüm 2' })).toHaveAttribute(
      'href',
      'https://www.youtube.com/watch?v=v2'
    );
  });

  it('sorts by newest first and by likes on demand', async () => {
    render(<CommentsPage />);

    await screen.findByText('Ayşe');
    expect(authors()).toEqual(['Ayşe', 'Zeynep', 'Mehmet']);

    fireEvent.change(screen.getByLabelText('Yorum sıralaması'), {
      target: { value: 'likes' },
    });
    await waitFor(() => expect(authors()).toEqual(['Zeynep', 'Ayşe', 'Mehmet']));

    fireEvent.change(screen.getByLabelText('Yorum sıralaması'), {
      target: { value: 'oldest' },
    });
    await waitFor(() => expect(authors()).toEqual(['Mehmet', 'Zeynep', 'Ayşe']));
  });

  it('filters unanswered comments and searches author or text', async () => {
    render(<CommentsPage />);

    await screen.findByText('Mehmet');

    await userEvent.click(screen.getByLabelText('Sadece yanıtlanmamış'));
    await waitFor(() => expect(authors()).toEqual(['Ayşe', 'Zeynep']));

    await userEvent.type(screen.getByPlaceholderText('Yazar veya yorum ara'), 'ses');
    await waitFor(() => expect(screen.queryAllByTestId('comment-author')).toHaveLength(0));

    await userEvent.clear(screen.getByPlaceholderText('Yazar veya yorum ara'));
    await userEvent.type(screen.getByPlaceholderText('Yazar veya yorum ara'), 'zeynep');
    await waitFor(() => expect(authors()).toEqual(['Zeynep']));
  });

  it('keeps write actions disabled without the comments capability', async () => {
    mockContext.connections = [connectionWith(false)];
    render(<CommentsPage />);

    await screen.findByText('Ayşe');

    expect(screen.getByText('Yorum yönetimi izni gerekiyor')).toBeInTheDocument();
    const replyButtons = screen.getAllByRole('button', { name: 'Yanıtla' });
    replyButtons.forEach((button) => expect(button).toBeDisabled());
    expect(api.replyToComment).not.toHaveBeenCalled();
    expect(api.moderateComment).not.toHaveBeenCalled();
  });
});
