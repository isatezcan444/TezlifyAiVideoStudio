import { CapabilityStatus, PlatformConnection } from '../types/account';

export type CapabilityName =
  | 'identity'
  | 'channel_read'
  | 'analytics'
  | 'upload'
  | 'comments'
  | 'revenue';

export const CAPABILITY_META: Record<
  CapabilityName,
  { label: string; description: string; grantLabel: string; optional?: boolean }
> = {
  identity: {
    label: 'Hesap kimliği',
    description: 'Google hesabını tanımlar.',
    grantLabel: 'Kimlik izni ver',
  },
  channel_read: {
    label: 'Kanal okuma',
    description: 'Kanal ve video verilerini okur.',
    grantLabel: 'Kanal izni ver',
  },
  analytics: {
    label: 'Analytics',
    description: 'Görüntüleme, izlenme ve abone metrikleri.',
    grantLabel: 'Analytics izni ver',
  },
  upload: {
    label: 'Video yükleme',
    description: 'Kanala video yükleme ve yayınlama.',
    grantLabel: 'YouTube yükleme izni ver',
  },
  comments: {
    label: 'Yorum yönetimi',
    description: 'Yorumlara yanıt verme ve moderasyon.',
    grantLabel: 'Yorum yönetimi izni ver',
  },
  revenue: {
    label: 'Gelir verisi',
    description: 'Tahmini reklam geliri (isteğe bağlı).',
    grantLabel: 'Gelir izni ekle',
    optional: true,
  },
};

export function findCapability(
  connection: PlatformConnection | null | undefined,
  capability: CapabilityName
): CapabilityStatus | undefined {
  return connection?.capabilities?.find((item) => item.capability === capability);
}

export function capabilityAllows(
  connection: PlatformConnection | null | undefined,
  capability: CapabilityName
): boolean {
  const status = findCapability(connection, capability);
  return status?.status === 'active';
}

export function capabilityNeedsScope(
  connection: PlatformConnection | null | undefined,
  capability: CapabilityName
): boolean {
  return findCapability(connection, capability)?.status === 'scope_required';
}
