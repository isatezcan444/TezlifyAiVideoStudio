import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  Box,
  Plus,
  Edit2,
  Trash2,
  Sparkles,
  Palette,
  Smile,
  Activity,
  Check,
  X,
  Search,
} from 'lucide-react';
import { Character, StudioAsset } from '../types/studio';
import { apiService } from '../services/api';
import { Button } from '../components/ui/button';
import { Spinner } from '../components/ui/Spinner';

export const CharacterStudioPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'characters' | 'assets'>('characters');

  // Characters state
  const [characters, setCharacters] = useState<Character[]>([]);
  const [isLoadingChars, setIsLoadingChars] = useState(true);
  const [charSearch, setCharSearch] = useState('');

  // Assets state
  const [assets, setAssets] = useState<StudioAsset[]>([]);
  const [isLoadingAssets, setIsLoadingAssets] = useState(true);
  const [assetCategory, setAssetCategory] = useState<string>('all');
  const [assetSearch, setAssetSearch] = useState('');

  // Edit/Create Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    gender: 'male' as 'male' | 'female' | 'neutral',
    skin_tone: '#F5D0A9',
    hair_color: '#2C1810',
    shirt_color: '#3B82F6',
    pants_color: '#1E293B',
    shoes_color: '#0F172A',
    hair_style: 'short_parted',
    default_expression: 'cheerful',
    default_pose: 'standing',
  });

  const fetchCharacters = useCallback(async () => {
    setIsLoadingChars(true);
    try {
      const res = await apiService.listCharacters(100, 0);
      setCharacters(res.items);
    } catch (err) {
      console.error('Karakterler yüklenemedi:', err);
    } finally {
      setIsLoadingChars(false);
    }
  }, []);

  const fetchAssets = useCallback(async () => {
    setIsLoadingAssets(true);
    try {
      const cat = assetCategory === 'all' ? undefined : assetCategory;
      const res = await apiService.listAssets(cat, 100, 0);
      setAssets(res.items);
    } catch (err) {
      console.error('Varlıklar yüklenemedi:', err);
    } finally {
      setIsLoadingAssets(false);
    }
  }, [assetCategory]);

  useEffect(() => {
    if (activeTab === 'characters') {
      fetchCharacters();
    } else {
      fetchAssets();
    }
  }, [activeTab, fetchCharacters, fetchAssets]);

  const handleOpenCreateModal = () => {
    setEditingCharacter(null);
    setFormData({
      name: '',
      description: '',
      gender: 'male',
      skin_tone: '#F5D0A9',
      hair_color: '#2C1810',
      shirt_color: '#3B82F6',
      pants_color: '#1E293B',
      shoes_color: '#0F172A',
      hair_style: 'short_parted',
      default_expression: 'cheerful',
      default_pose: 'standing',
    });
    setErrorMsg(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (char: Character) => {
    setEditingCharacter(char);
    setFormData({
      name: char.name,
      description: char.description || '',
      gender: char.gender,
      skin_tone: char.palette.skin_tone,
      hair_color: char.palette.hair_color,
      shirt_color: char.palette.shirt_color,
      pants_color: char.palette.pants_color,
      shoes_color: char.palette.shoes_color,
      hair_style: char.hair_style,
      default_expression: char.default_expression,
      default_pose: char.default_pose,
    });
    setErrorMsg(null);
    setIsModalOpen(true);
  };

  const handleSaveCharacter = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setErrorMsg('Karakter adı zorunludur.');
      return;
    }

    setIsSaving(true);
    setErrorMsg(null);

    const payload = {
      name: formData.name.trim(),
      description: formData.description.trim(),
      gender: formData.gender,
      hair_style: formData.hair_style,
      default_expression: formData.default_expression,
      default_pose: formData.default_pose,
      palette: {
        skin_tone: formData.skin_tone,
        hair_color: formData.hair_color,
        shirt_color: formData.shirt_color,
        pants_color: formData.pants_color,
        shoes_color: formData.shoes_color,
        eye_color: '#1E293B',
      },
    };

    try {
      if (editingCharacter) {
        await apiService.updateCharacter(editingCharacter.id, payload);
      } else {
        await apiService.createCharacter(payload);
      }
      setIsModalOpen(false);
      fetchCharacters();
    } catch (err: any) {
      setErrorMsg(err.message || 'Karakter kaydedilemedi.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCharacter = async (char: Character) => {
    if (char.is_builtin) return;
    if (!confirm(`'${char.name}' karakterini silmek istediğinize emin misiniz?`)) return;

    try {
      await apiService.deleteCharacter(char.id);
      fetchCharacters();
    } catch (err: any) {
      alert(err.message || 'Karakter silinemedi.');
    }
  };

  const filteredCharacters = characters.filter((c) =>
    c.name.toLowerCase().includes(charSearch.toLowerCase()) ||
    c.description.toLowerCase().includes(charSearch.toLowerCase())
  );

  const filteredAssets = assets.filter((a) =>
    a.name.toLowerCase().includes(assetSearch.toLowerCase()) ||
    a.id.toLowerCase().includes(assetSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Header / Navigation Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 dark:border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-[#7367F0]" />
            Karakter ve Sahne Varlıkları Stüdyosu
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Blender 5.2.3 ile tam uyumlu 2.5D cutout karakterler, yüz ifadeleri, pozlar ve sahne eşyaları kütüphanesi.
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-2 bg-gray-100 dark:bg-gray-800/60 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('characters')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'characters'
                ? 'bg-white dark:bg-[#7367F0] text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Users className="w-4 h-4" />
            Karakterler ({characters.length})
          </button>
          <button
            onClick={() => setActiveTab('assets')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'assets'
                ? 'bg-white dark:bg-[#7367F0] text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Box className="w-4 h-4" />
            Sahne Varlıkları ({assets.length})
          </button>
        </div>
      </div>

      {/* TAB 1: CHARACTERS */}
      {activeTab === 'characters' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            {/* Search Input */}
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
              <input
                type="text"
                placeholder="Karakter ara..."
                value={charSearch}
                onChange={(e) => setCharSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]"
              />
            </div>

            <Button
              onClick={handleOpenCreateModal}
              className="w-full sm:w-auto bg-[#7367F0] hover:bg-[#6255e4] text-white flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Yeni Karakter Oluştur
            </Button>
          </div>

          {isLoadingChars ? (
            <div className="flex justify-center items-center py-16">
              <Spinner className="w-8 h-8 text-[#7367F0]" />
            </div>
          ) : filteredCharacters.length === 0 ? (
            <div className="text-center py-16 bg-white dark:bg-gray-900/50 rounded-2xl border border-gray-200 dark:border-gray-800">
              <Users className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400">Hiç karakter bulunamadı.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredCharacters.map((char) => (
                <div
                  key={char.id}
                  className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col"
                >
                  {/* Thumbnail Container */}
                  <div className="relative aspect-square bg-gradient-to-b from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-950 flex items-center justify-center overflow-hidden">
                    <img
                      src={apiService.getCharacterThumbnailUrl(char.id)}
                      alt={char.name}
                      className="w-full h-full object-contain p-2 hover:scale-105 transition-transform duration-300"
                      onError={(e) => {
                        // Fallback placeholder if image not rendered yet
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />

                    {/* Builtin Badge */}
                    <div className="absolute top-3 left-3 flex gap-2">
                      {char.is_builtin && (
                        <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-[#7367F0]/20 text-[#7367F0] border border-[#7367F0]/30 backdrop-blur-sm">
                          Hazır Karakter
                        </span>
                      )}
                      <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-black/40 text-white backdrop-blur-sm capitalize">
                        {char.gender === 'male' ? 'Erkek' : char.gender === 'female' ? 'Kadın' : 'Nötr'}
                      </span>
                    </div>

                    {/* Expression & Pose Badge */}
                    <div className="absolute bottom-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/50 text-white text-xs backdrop-blur-sm">
                      <Smile className="w-3.5 h-3.5 text-amber-400" />
                      <span className="capitalize">{char.default_expression}</span>
                    </div>
                  </div>

                  {/* Info Body */}
                  <div className="p-4 flex-1 flex flex-col justify-between space-y-4">
                    <div>
                      <h3 className="font-bold text-gray-900 dark:text-white text-base">{char.name}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                        {char.description || 'Açıklama belirtilmedi.'}
                      </p>

                      {/* Color Palette Preview Swatches */}
                      <div className="flex items-center gap-1.5 mt-3">
                        <span className="text-[11px] text-gray-400 mr-1">Renkler:</span>
                        <div
                          className="w-4 h-4 rounded-full border border-black/20"
                          style={{ backgroundColor: char.palette.skin_tone }}
                          title={`Ten: ${char.palette.skin_tone}`}
                        />
                        <div
                          className="w-4 h-4 rounded-full border border-black/20"
                          style={{ backgroundColor: char.palette.hair_color }}
                          title={`Saç: ${char.palette.hair_color}`}
                        />
                        <div
                          className="w-4 h-4 rounded-full border border-black/20"
                          style={{ backgroundColor: char.palette.shirt_color }}
                          title={`Üst: ${char.palette.shirt_color}`}
                        />
                        <div
                          className="w-4 h-4 rounded-full border border-black/20"
                          style={{ backgroundColor: char.palette.pants_color }}
                          title={`Alt: ${char.palette.pants_color}`}
                        />
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleOpenEditModal(char)}
                        className="text-xs flex items-center gap-1.5"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                        Düzenle
                      </Button>
                      {!char.is_builtin && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDeleteCharacter(char)}
                          className="text-xs text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: ASSETS */}
      {activeTab === 'assets' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            {/* Search Input */}
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
              <input
                type="text"
                placeholder="Varlık veya sahne eşyası ara..."
                value={assetSearch}
                onChange={(e) => setAssetSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]"
              />
            </div>

            {/* Category Pills */}
            <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1">
              {[
                { id: 'all', label: 'Tümü' },
                { id: 'background', label: 'Arka Planlar' },
                { id: 'prop', label: 'Sahne Eşyaları' },
                { id: 'lighting', label: 'Işıklandırma' },
              ].map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setAssetCategory(cat.id)}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                    assetCategory === cat.id
                      ? 'bg-[#7367F0] text-white shadow-sm'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {isLoadingAssets ? (
            <div className="flex justify-center items-center py-16">
              <Spinner className="w-8 h-8 text-[#7367F0]" />
            </div>
          ) : filteredAssets.length === 0 ? (
            <div className="text-center py-16 bg-white dark:bg-gray-900/50 rounded-2xl border border-gray-200 dark:border-gray-800">
              <Box className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400">Bu kategoride varlık bulunamadı.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredAssets.map((asset) => (
                <div
                  key={asset.id}
                  className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col"
                >
                  {/* Thumbnail Container */}
                  <div className="relative aspect-video bg-gradient-to-b from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-950 flex items-center justify-center overflow-hidden">
                    <img
                      src={apiService.getAssetThumbnailUrl(asset.id)}
                      alt={asset.name}
                      className="w-full h-full object-contain p-2 hover:scale-105 transition-transform duration-300"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />

                    {/* Category Badge */}
                    <div className="absolute top-3 left-3">
                      <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-black/50 text-white backdrop-blur-sm capitalize">
                        {asset.category === 'background' ? 'Arka Plan' : asset.category === 'prop' ? 'Prop' : 'Işık'}
                      </span>
                    </div>

                    <div className="absolute bottom-3 right-3">
                      <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-black/60 text-gray-300 backdrop-blur-sm">
                        {asset.id}
                      </span>
                    </div>
                  </div>

                  {/* Info Body */}
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="font-bold text-gray-900 dark:text-white text-base">{asset.name}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                        {asset.description}
                      </p>
                    </div>

                    {/* Tags */}
                    <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                      {asset.tags.map((t) => (
                        <span
                          key={t}
                          className="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300"
                        >
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* CREATE / EDIT CHARACTER MODAL */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-1 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#7367F0]" />
              {editingCharacter ? `'${editingCharacter.name}' Karakterini Özelleştir` : 'Yeni Karakter Oluştur'}
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-6">
              Karakterin saç, ten, kıyafet renklerini, varsayılan pozunu ve yüz ifadesini ayarlayın.
            </p>

            {errorMsg && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-xl text-red-600 dark:text-red-400 text-xs">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleSaveCharacter} className="space-y-4">
              {/* Name & Gender */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Karakter Adı *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-sm focus:ring-2 focus:ring-[#7367F0] focus:outline-none"
                    placeholder="Örn: Ali"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Cinsiyet / Tip
                  </label>
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData({ ...formData, gender: e.target.value as any })}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-sm focus:ring-2 focus:ring-[#7367F0] focus:outline-none"
                  >
                    <option value="male">Erkek</option>
                    <option value="female">Kadın</option>
                    <option value="neutral">Nötr</option>
                  </select>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Açıklama & Arketip
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-sm focus:ring-2 focus:ring-[#7367F0] focus:outline-none"
                  placeholder="Örn: Neşeli ve komik kafe müdavimi"
                />
              </div>

              {/* Appearance Colors */}
              <div className="border-t border-gray-100 dark:border-gray-800 pt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5 text-[#7367F0]" />
                  Renk ve Görünüş Paleti
                </h4>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-gray-500 mb-1">Ten Tonu</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.skin_tone}
                        onChange={(e) => setFormData({ ...formData, skin_tone: e.target.value })}
                        className="w-8 h-8 rounded-lg border-0 cursor-pointer p-0 bg-transparent"
                      />
                      <span className="text-xs font-mono">{formData.skin_tone}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] text-gray-500 mb-1">Saç Rengi</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.hair_color}
                        onChange={(e) => setFormData({ ...formData, hair_color: e.target.value })}
                        className="w-8 h-8 rounded-lg border-0 cursor-pointer p-0 bg-transparent"
                      />
                      <span className="text-xs font-mono">{formData.hair_color}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] text-gray-500 mb-1">Üst / Gömlek</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.shirt_color}
                        onChange={(e) => setFormData({ ...formData, shirt_color: e.target.value })}
                        className="w-8 h-8 rounded-lg border-0 cursor-pointer p-0 bg-transparent"
                      />
                      <span className="text-xs font-mono">{formData.shirt_color}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] text-gray-500 mb-1">Pantolon</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.pants_color}
                        onChange={(e) => setFormData({ ...formData, pants_color: e.target.value })}
                        className="w-8 h-8 rounded-lg border-0 cursor-pointer p-0 bg-transparent"
                      />
                      <span className="text-xs font-mono">{formData.pants_color}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] text-gray-500 mb-1">Ayakkabı</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.shoes_color}
                        onChange={(e) => setFormData({ ...formData, shoes_color: e.target.value })}
                        className="w-8 h-8 rounded-lg border-0 cursor-pointer p-0 bg-transparent"
                      />
                      <span className="text-xs font-mono">{formData.shoes_color}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] text-gray-500 mb-1">Saç Modeli</label>
                    <select
                      value={formData.hair_style}
                      onChange={(e) => setFormData({ ...formData, hair_style: e.target.value })}
                      className="w-full px-2 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs"
                    >
                      <option value="short_parted">Kısa Yandan Ayrık</option>
                      <option value="bob_cut">Küt / Bob Kesim</option>
                      <option value="long_straight">Uzun Düz</option>
                      <option value="curly">Kıvırcık</option>
                      <option value="ponytail">At Kuyruğu</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Expression & Pose */}
              <div className="border-t border-gray-100 dark:border-gray-800 pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 flex items-center gap-1.5">
                    <Smile className="w-3.5 h-3.5 text-amber-500" />
                    Varsayılan Yüz İfadesi
                  </label>
                  <select
                    value={formData.default_expression}
                    onChange={(e) => setFormData({ ...formData, default_expression: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-sm"
                  >
                    <option value="neutral">Nötr (Neutral)</option>
                    <option value="cheerful">Neşeli / Güler Yüzlü (Cheerful)</option>
                    <option value="surprised">Şaşkın (Surprised)</option>
                    <option value="angry">Kızgın (Angry)</option>
                    <option value="sad">Üzgün (Sad)</option>
                    <option value="thinking">Düşünceli (Thinking)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-emerald-500" />
                    Varsayılan Duruş / Poz
                  </label>
                  <select
                    value={formData.default_pose}
                    onChange={(e) => setFormData({ ...formData, default_pose: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-sm"
                  >
                    <option value="standing">Ayakta (Standing)</option>
                    <option value="sitting">Oturarak (Sitting)</option>
                    <option value="sitting_table">Masada Oturarak (Sitting Table)</option>
                    <option value="walking">Yürürken (Walking)</option>
                    <option value="gesturing">Jest / El Hareketi (Gesturing)</option>
                    <option value="pointing">İşaret Ederek (Pointing)</option>
                    <option value="idle">Rahat / Bekleme (Idle)</option>
                  </select>
                </div>
              </div>

              {/* Form Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100 dark:border-gray-800">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isSaving}
                >
                  İptal
                </Button>
                <Button
                  type="submit"
                  disabled={isSaving}
                  className="bg-[#7367F0] hover:bg-[#6255e4] text-white flex items-center gap-2"
                >
                  {isSaving ? <Spinner className="w-4 h-4 text-white" /> : <Check className="w-4 h-4" />}
                  {editingCharacter ? 'Değişiklikleri Kaydet' : 'Karakteri Oluştur'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
