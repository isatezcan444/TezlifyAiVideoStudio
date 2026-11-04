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
  Film,
  Play,
  Clock,
  CheckCircle2,
  AlertCircle,
  Layers,
  Mic,
  Volume2,
} from 'lucide-react';
import {
  Character,
  StudioAsset,
  RenderJob,
  StudioProject,
  VoiceProfile,
  VoiceStatusResponse,
} from '../types/studio';
import { apiService } from '../services/api';
import { Button } from '../components/ui/button';
import { Spinner } from '../components/ui/Spinner';

export const CharacterStudioPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'characters' | 'assets' | 'renders'>('characters');

  // ElevenLabs Voice state (Stage 4.4)
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusResponse | null>(null);
  const [synthesizeVoices, setSynthesizeVoices] = useState<boolean>(true);
  const [playingAudioUrl, setPlayingAudioUrl] = useState<string | null>(null);

  // Characters state
  const [characters, setCharacters] = useState<Character[]>([]);
  const [isLoadingChars, setIsLoadingChars] = useState(true);
  const [charSearch, setCharSearch] = useState('');

  // Assets state
  const [assets, setAssets] = useState<StudioAsset[]>([]);
  const [isLoadingAssets, setIsLoadingAssets] = useState(true);
  const [assetCategory, setAssetCategory] = useState<string>('all');
  const [assetSearch, setAssetSearch] = useState('');

  // Render & Animation Studio State (Stage 4.3)
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [selectedProject, setSelectedProject] = useState<StudioProject | null>(null);
  const [, setIsLoadingProjects] = useState(false);
  const [currentJob, setCurrentJob] = useState<RenderJob | null>(null);
  const [projectRenders, setProjectRenders] = useState<RenderJob[]>([]);
  const [isStartingRender, setIsStartingRender] = useState(false);
  const [selectedEngine, setSelectedEngine] = useState<'BLENDER_WORKBENCH' | 'BLENDER_EEVEE'>('BLENDER_WORKBENCH');
  const [newStoryPrompt, setNewStoryPrompt] = useState('Ali ve Ayşe modern bir kafede buluşuyor. Ali kahve ısmarlıyor ve gülerek sohbet ediyorlar. Video 15 saniye sürsün.');
  const [isGeneratingStory, setIsGeneratingStory] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

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
    voice_id: 'IKne3meq5aSn9XLyUdCD',
    skin_tone: '#F5D0A9',
    hair_color: '#2C1810',
    shirt_color: '#3B82F6',
    pants_color: '#1E293B',
    shoes_color: '#0F172A',
    hair_style: 'short_parted',
    default_expression: 'cheerful',
    default_pose: 'standing',
  });

  const fetchVoiceStatusAndList = useCallback(async () => {
    try {
      const [statusRes, listRes] = await Promise.all([
        apiService.getVoiceStatus().catch(() => null),
        apiService.listVoices().catch(() => null),
      ]);
      if (statusRes) setVoiceStatus(statusRes);
      if (listRes && listRes.items) setVoices(listRes.items);
    } catch (err) {
      console.error('Ses servisi yüklenemedi:', err);
    }
  }, []);

  const handleTogglePreview = (previewUrl?: string | null) => {
    if (!previewUrl) return;
    if (playingAudioUrl === previewUrl) {
      setPlayingAudioUrl(null);
    } else {
      setPlayingAudioUrl(previewUrl);
      const audio = new Audio(previewUrl);
      audio.onended = () => setPlayingAudioUrl(null);
      audio.onerror = () => setPlayingAudioUrl(null);
      audio.play().catch(() => setPlayingAudioUrl(null));
    }
  };

  useEffect(() => {
    fetchVoiceStatusAndList();
  }, [fetchVoiceStatusAndList]);

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

  const fetchProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    try {
      const res = await apiService.listProjects(50, 0);
      setProjects(res.items);
      if (res.items.length > 0 && !selectedProject) {
        setSelectedProject(res.items[0]);
      }
    } catch (err) {
      console.error('Projeler yüklenemedi:', err);
    } finally {
      setIsLoadingProjects(false);
    }
  }, [selectedProject]);

  const fetchProjectRenders = useCallback(async (projId: string) => {
    try {
      const res = await apiService.listProjectRenders(projId);
      setProjectRenders(res.items);
      if (res.items.length > 0) {
        setCurrentJob(res.items[0]);
      }
    } catch (err) {
      console.error('Render geçmişi yüklenemedi:', err);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'characters') {
      fetchCharacters();
    } else if (activeTab === 'assets') {
      fetchAssets();
    } else if (activeTab === 'renders') {
      fetchProjects();
    }
  }, [activeTab, fetchCharacters, fetchAssets, fetchProjects]);

  useEffect(() => {
    if (selectedProject) {
      fetchProjectRenders(selectedProject.id);
    }
  }, [selectedProject, fetchProjectRenders]);

  // Real-time polling for active render jobs
  useEffect(() => {
    if (!currentJob) return;
    if (currentJob.status !== 'pending' && currentJob.status !== 'running') return;

    const intervalId = setInterval(async () => {
      try {
        const updated = await apiService.getRenderJob(currentJob.id);
        setCurrentJob(updated);
        if (updated.status === 'completed' || updated.status === 'failed') {
          if (selectedProject) {
            fetchProjectRenders(selectedProject.id);
          }
        }
      } catch (err) {
        console.error('Render polling error:', err);
      }
    }, 2000);

    return () => clearInterval(intervalId);
  }, [currentJob, selectedProject, fetchProjectRenders]);

  const handleGenerateStoryProject = async () => {
    if (!newStoryPrompt.trim()) return;
    setIsGeneratingStory(true);
    setRenderError(null);
    try {
      const res = await apiService.generateStory({
        prompt: newStoryPrompt.trim(),
        target_duration_seconds: 15.0,
      });
      const createdProj = await apiService.createProject({
        title: res.title || 'Yeni AI Animasyon Sahnesi',
        description: res.description || newStoryPrompt.trim(),
        scene_graph: res,
      });
      setSelectedProject(createdProj);
      await fetchProjects();
    } catch (err: any) {
      setRenderError(err.message || 'Senaryo ve proje üretilemedi.');
    } finally {
      setIsGeneratingStory(false);
    }
  };

  const handleStartRender = async () => {
    if (!selectedProject) return;
    setIsStartingRender(true);
    setRenderError(null);
    try {
      const job = await apiService.startProjectRender(selectedProject.id, selectedEngine, synthesizeVoices);
      setCurrentJob(job);
      await fetchProjectRenders(selectedProject.id);
    } catch (err: any) {
      setRenderError(err.message || 'Render başlatılamadı.');
    } finally {
      setIsStartingRender(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingCharacter(null);
    setFormData({
      name: '',
      description: '',
      gender: 'male',
      voice_id: 'IKne3meq5aSn9XLyUdCD',
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
      voice_id: char.voice_id || (char.gender === 'female' ? 'cgSgspJ2msm6clMCkdW9' : 'IKne3meq5aSn9XLyUdCD'),
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
      voice_id: formData.voice_id,
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
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-gray-200 dark:border-gray-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-[#7367F0]" />
              Karakter ve Sahne Varlıkları Stüdyosu
            </h1>
            {/* ElevenLabs Status Badge */}
            {voiceStatus?.is_configured ? (
              <span
                className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                title={`ElevenLabs Bağlı - ${voiceStatus.default_model} (${voices.length} ses)`}
              >
                <Mic className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>ElevenLabs Bağlı ({voices.length} Ses)</span>
              </span>
            ) : (
              <span
                className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                title="ELEVENLABS_API_KEY .env dosyasında henüz tanımlanmadı"
              >
                <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                <span>ElevenLabs API Anahtarı Gerekli (.env)</span>
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Blender 5.2.3 ile tam uyumlu 2.5D cutout karakterler, yüz ifadeleri, pozlar, sesler ve sahne eşyaları.
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-2 bg-gray-100 dark:bg-gray-800/60 p-1 rounded-xl shrink-0">
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
          <button
            onClick={() => setActiveTab('renders')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'renders'
                ? 'bg-white dark:bg-[#7367F0] text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Film className="w-4 h-4" />
            Blender Render Motoru
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

                      {/* Voice Badge */}
                      <div className="flex items-center gap-1.5 mt-2">
                        <span className="text-[11px] text-gray-400">Ses:</span>
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                          <Mic className="w-3 h-3 text-[#7367F0]" />
                          {char.name === 'Ali'
                            ? 'Charlie (Erkek)'
                            : char.name === 'Ayşe'
                            ? 'Jessica (Kadın)'
                            : (voices.find((v) => v.voice_id === char.voice_id)?.name || char.voice_id || 'Varsayılan')}
                        </span>
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

      {/* TAB 3: BLENDER RENDER ENGINE (Stage 4.3) */}
      {activeTab === 'renders' && (
        <div className="space-y-6">
          {/* Studio Header Bar */}
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#7367F0]/10 text-[#7367F0] flex items-center justify-center shrink-0">
                  <Film className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                    Blender Headless Animasyon & Video Render Motoru
                  </h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    SceneGraph sahnelerini Blender 5.2.3 ile arka planda işleyip MP4 videoya dönüştürür.
                  </p>
                </div>
              </div>

              {/* Project Selection / Create */}
              <div className="flex flex-wrap items-center gap-3">
                {projects.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Proje:</span>
                    <select
                      value={selectedProject?.id || ''}
                      onChange={(e) => {
                        const p = projects.find((x) => x.id === e.target.value);
                        if (p) setSelectedProject(p);
                      }}
                      className="px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white"
                    >
                      {projects.map((proj) => (
                        <option key={proj.id} value={proj.id}>
                          {proj.title} ({proj.scene_count} sahne, {proj.total_duration_seconds}s)
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>

            {renderError && (
              <div className="mt-4 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-xl text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{renderError}</span>
              </div>
            )}
          </div>

          {/* Quick Scene Creation / Prompt Input */}
          {(!selectedProject || projects.length === 0) && (
            <div className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-gray-900 dark:to-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 rounded-2xl p-6">
              <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5 text-[#7367F0]" />
                Hızlı Sahne Senaryosu Oluştur
              </h3>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-4">
                Animasyon oluşturmak için karakterleri, mekanı ve diyalogları tarif eden kısa bir fikir yazın.
              </p>

              <div className="space-y-3">
                <textarea
                  value={newStoryPrompt}
                  onChange={(e) => setNewStoryPrompt(e.target.value)}
                  rows={3}
                  placeholder="Örn: Ali ve Ayşe modern kafede kahve içerken buluşuyor..."
                  className="w-full px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]"
                />
                <Button
                  onClick={handleGenerateStoryProject}
                  disabled={isGeneratingStory}
                  className="bg-[#7367F0] hover:bg-[#6255e4] text-white flex items-center gap-2 text-xs"
                >
                  {isGeneratingStory ? <Spinner className="w-4 h-4 text-white" /> : <Play className="w-4 h-4" />}
                  {isGeneratingStory ? 'Senaryo Oluşturuluyor...' : 'Senaryo & Proje Oluştur'}
                </Button>
              </div>
            </div>
          )}

          {/* Main 2-Column Studio Grid */}
          {selectedProject && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column (5 cols): Project Details & Render Controls */}
              <div className="lg:col-span-5 space-y-6">
                {/* Render Dispatch Card */}
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-gray-900 dark:text-white text-sm flex items-center gap-2">
                      <Layers className="w-4 h-4 text-[#7367F0]" />
                      Render Kontrolleri
                    </h3>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
                      Blender 5.2.3
                    </span>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Render Motoru Modu
                    </label>
                    <select
                      value={selectedEngine}
                      onChange={(e) => setSelectedEngine(e.target.value as any)}
                      className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium"
                    >
                      <option value="BLENDER_WORKBENCH">
                        Workbench (Hızlı 2.5D Shading - Önerilen)
                      </option>
                      <option value="BLENDER_EEVEE">
                        Eevee (Işıklandırma ve Gölgeler)
                      </option>
                    </select>
                    <p className="text-[11px] text-gray-400 mt-1">
                      Workbench, 1080p 30 FPS kareleri saniyeler içinde render eder.
                    </p>
                  </div>

                  {/* ElevenLabs Voice Synthesis Toggle */}
                  <div className="p-3 bg-purple-50/60 dark:bg-purple-950/20 border border-purple-100 dark:border-purple-900/30 rounded-xl space-y-2">
                    <label className="flex items-center justify-between cursor-pointer">
                      <div className="flex items-center gap-2">
                        <Mic className="w-4 h-4 text-[#7367F0]" />
                        <span className="text-xs font-semibold text-gray-900 dark:text-white">
                          ElevenLabs AI Ses Sentezi
                        </span>
                      </div>
                      <input
                        type="checkbox"
                        checked={synthesizeVoices}
                        onChange={(e) => setSynthesizeVoices(e.target.checked)}
                        className="w-4 h-4 text-[#7367F0] rounded border-gray-300 focus:ring-[#7367F0]"
                      />
                    </label>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400">
                      Diyalog metinlerini karakterlerin ses profilleriyle MP3 olarak sentezler ve animasyon ağız hareketleriyle senkronize eder.
                    </p>

                    {synthesizeVoices && (
                      <div className="pt-2 border-t border-purple-100/60 dark:border-purple-900/20 flex flex-wrap items-center gap-2">
                        <span className="text-[10px] text-gray-400 font-medium">Sahne Sesleri:</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 font-mono">
                          Ali: Charlie (IKne3...)
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-pink-100 dark:bg-pink-950/40 text-pink-700 dark:text-pink-300 font-mono">
                          Ayşe: Jessica (cgSg...)
                        </span>
                      </div>
                    )}
                  </div>

                  <Button
                    onClick={handleStartRender}
                    disabled={isStartingRender || (currentJob?.status === 'running' || currentJob?.status === 'pending')}
                    className="w-full bg-[#7367F0] hover:bg-[#6255e4] text-white py-2.5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-md shadow-[#7367F0]/20"
                  >
                    {isStartingRender ? (
                      <Spinner className="w-4 h-4 text-white" />
                    ) : (
                      <Play className="w-4 h-4 fill-white" />
                    )}
                    {isStartingRender ? 'Render Başlatılıyor...' : 'Blender ile Videoyu Render Et'}
                  </Button>
                </div>

                {/* Project Info & SceneGraph Summary */}
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs space-y-4">
                  <h3 className="font-bold text-gray-900 dark:text-white text-sm">
                    {selectedProject.title}
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {selectedProject.description || 'Açıklama belirtilmemiş.'}
                  </p>

                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-100 dark:border-gray-800 text-xs">
                    <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                      <span className="text-gray-400 block text-[10px]">Toplam Süre</span>
                      <span className="font-bold text-gray-900 dark:text-white">
                        {selectedProject.total_duration_seconds} saniye
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                      <span className="text-gray-400 block text-[10px]">Sahne Sayısı</span>
                      <span className="font-bold text-gray-900 dark:text-white">
                        {selectedProject.scene_count} Sahne
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                      <span className="text-gray-400 block text-[10px]">Karakterler</span>
                      <span className="font-bold text-gray-900 dark:text-white">
                        {selectedProject.character_count} Karakter
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                      <span className="text-gray-400 block text-[10px]">Format / Çözünürlük</span>
                      <span className="font-bold text-gray-900 dark:text-white">
                        1920x1080 @ 30fps
                      </span>
                    </div>
                  </div>

                  {/* Scene details */}
                  {selectedProject.scene_graph?.scenes && (
                    <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                      <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                        Sahne Zaman Çizelgesi
                      </span>
                      {selectedProject.scene_graph.scenes.map((s: any, idx: number) => (
                        <div
                          key={s.scene_id || idx}
                          className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-xs space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-gray-900 dark:text-white">
                              Sahne {idx + 1}: {s.scene_id}
                            </span>
                            <span className="text-[10px] px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                              {s.duration_seconds}s
                            </span>
                          </div>
                          <div className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center gap-3">
                            <span>Arka Plan: <strong>{s.background?.asset_id || 'Modern Kafe'}</strong></span>
                            <span>Kamera: <strong>{s.camera?.angle || 'Two Shot'}</strong></span>
                          </div>
                          {s.dialogues && s.dialogues.length > 0 && (
                            <div className="text-[11px] text-gray-600 dark:text-gray-300 italic border-l-2 border-[#7367F0] pl-2 mt-1">
                              "{s.dialogues[0].text}"
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column (7 cols): Live Render Status, Playable Video & History */}
              <div className="lg:col-span-7 space-y-6">
                {/* Active Render Progress Card */}
                {currentJob && (currentJob.status === 'running' || currentJob.status === 'pending') && (
                  <div className="bg-white dark:bg-gray-900 border-2 border-[#7367F0]/40 rounded-2xl p-6 shadow-md space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Spinner className="w-5 h-5 text-[#7367F0]" />
                        <h4 className="font-bold text-sm text-gray-900 dark:text-white">
                          Render Devam Ediyor...
                        </h4>
                      </div>
                      <span className="text-xs font-mono font-bold text-[#7367F0]">
                        %{Math.round(currentJob.progress_percent)}
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-gray-100 dark:bg-gray-800 h-3 rounded-full overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-[#7367F0] to-[#9E95F5] h-full rounded-full transition-all duration-300"
                        style={{ width: `${Math.max(5, currentJob.progress_percent)}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                      <span className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5" />
                        {currentJob.current_step}
                      </span>
                      <span className="font-mono text-[10px]">ID: {currentJob.id}</span>
                    </div>
                  </div>
                )}

                {/* Render Failed Card */}
                {currentJob && currentJob.status === 'failed' && (
                  <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-2xl p-5 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <h4 className="font-bold text-sm text-red-700 dark:text-red-300">
                        Render Başarısız Oldu
                      </h4>
                      <p className="text-xs text-red-600 dark:text-red-400 font-mono">
                        {currentJob.error_message || 'Bilinmeyen hata'}
                      </p>
                    </div>
                  </div>
                )}

                {/* Video Player Card (Completed) */}
                {currentJob && currentJob.status === 'completed' && currentJob.output_video_path && (
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                        <h4 className="font-bold text-sm text-gray-900 dark:text-white">
                          Render Edilen Animasyon Videosu
                        </h4>
                      </div>
                      <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
                        Başarılı
                      </span>
                    </div>

                    {/* HTML5 Video Player */}
                    <div className="rounded-xl overflow-hidden bg-black shadow-lg border border-gray-800">
                      <video
                        key={currentJob.id}
                        controls
                        autoPlay
                        className="w-full aspect-video"
                        src={apiService.getRenderVideoUrl(currentJob.id)}
                      >
                        Tarayıcınız video oynatmayı desteklemiyor.
                      </video>
                    </div>

                    {/* Technical Parameter Breakdown */}
                    {currentJob.output_metadata && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-gray-100 dark:border-gray-800 text-xs">
                        <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                          <span className="text-gray-400 block text-[10px]">Çözünürlük</span>
                          <span className="font-bold text-gray-900 dark:text-white">
                            {currentJob.output_metadata.width}x{currentJob.output_metadata.height}
                          </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                          <span className="text-gray-400 block text-[10px]">FPS / Süre</span>
                          <span className="font-bold text-gray-900 dark:text-white">
                            {currentJob.output_metadata.fps} FPS · {currentJob.output_metadata.duration_seconds.toFixed(1)}s
                          </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                          <span className="text-gray-400 block text-[10px]">Codec / Format</span>
                          <span className="font-bold text-gray-900 dark:text-white">
                            {currentJob.output_metadata.video_codec.toUpperCase()} · {currentJob.output_metadata.pixel_format}
                          </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60">
                          <span className="text-gray-400 block text-[10px]">Render Süresi</span>
                          <span className="font-bold text-gray-900 dark:text-white">
                            {currentJob.output_metadata.render_duration_seconds}s
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Render History Table */}
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-xs space-y-3">
                  <h4 className="font-bold text-xs text-gray-400 uppercase tracking-wider">
                    Render Geçmişi ({projectRenders.length})
                  </h4>

                  {projectRenders.length === 0 ? (
                    <p className="text-xs text-gray-400 py-3 text-center">
                      Bu proje için henüz render alınmamış.
                    </p>
                  ) : (
                    <div className="divide-y divide-gray-100 dark:divide-gray-800">
                      {projectRenders.map((job) => (
                        <div
                          key={job.id}
                          className="py-3 flex items-center justify-between gap-3 text-xs"
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-gray-900 dark:text-white">
                                {job.id}
                              </span>
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                  job.status === 'completed'
                                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                                    : job.status === 'failed'
                                    ? 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400'
                                    : 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                                }`}
                              >
                                {job.status.toUpperCase()}
                              </span>
                            </div>
                            <span className="text-[11px] text-gray-400">
                              {new Date(job.created_at).toLocaleString('tr-TR')}
                            </span>
                          </div>

                          {job.status === 'completed' && job.output_video_path && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setCurrentJob(job)}
                              className="text-xs flex items-center gap-1.5"
                            >
                              <Play className="w-3.5 h-3.5" />
                              İzle
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
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

              {/* ElevenLabs Voice Selection */}
              <div className="border-t border-gray-100 dark:border-gray-800 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                    <Mic className="w-3.5 h-3.5 text-[#7367F0]" />
                    ElevenLabs AI Ses Profili
                  </label>
                  {voiceStatus?.is_configured ? (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                      API Aktif
                    </span>
                  ) : (
                    <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                      .env API Anahtarı Gerekli
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={formData.voice_id}
                    onChange={(e) => setFormData({ ...formData, voice_id: e.target.value })}
                    className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium focus:ring-2 focus:ring-[#7367F0] focus:outline-none"
                  >
                    <option value="IKne3meq5aSn9XLyUdCD">Charlie (Erkek - Dinamik / Doğal - Önerilen: Ali)</option>
                    <option value="cgSgspJ2msm6clMCkdW9">Jessica (Kadın - Sıcak / Samimi - Önerilen: Ayşe)</option>
                    <option value="pNInz6obpgDQGcFmaJgB">Adam (Erkek - Derin / Anlatıcı)</option>
                    <option value="EXAVITQu4vr4xnSDxMaL">Sarah (Kadın - Yumuşak / Profesyonel)</option>
                    <option value="bIHbv24MWmeRgasZH58o">Will (Erkek - Genç / Rahat)</option>
                    <option value="Xb7hH8MSUJpSbSDYk0k2">Alice (Kadın - Canlı / Akıcı)</option>
                    {voices
                      .filter(
                        (v) =>
                          ![
                            'IKne3meq5aSn9XLyUdCD',
                            'cgSgspJ2msm6clMCkdW9',
                            'pNInz6obpgDQGcFmaJgB',
                            'EXAVITQu4vr4xnSDxMaL',
                            'bIHbv24MWmeRgasZH58o',
                            'Xb7hH8MSUJpSbSDYk0k2',
                          ].includes(v.voice_id)
                      )
                      .map((v) => (
                        <option key={v.voice_id} value={v.voice_id}>
                          {v.name} ({v.gender || 'Genel'}) - {v.voice_id.slice(0, 8)}...
                        </option>
                      ))}
                  </select>

                  {/* Audio preview button if preview_url is available */}
                  {(() => {
                    const matchedVoice = voices.find((v) => v.voice_id === formData.voice_id);
                    if (matchedVoice?.preview_url) {
                      return (
                        <button
                          type="button"
                          onClick={() => handleTogglePreview(matchedVoice.preview_url)}
                          className={`px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 border transition-colors ${
                            playingAudioUrl === matchedVoice.preview_url
                              ? 'bg-[#7367F0] text-white border-[#7367F0]'
                              : 'bg-purple-50 hover:bg-purple-100 dark:bg-purple-950/40 dark:hover:bg-purple-900/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800'
                          }`}
                          title="Ses Örneğini Dinle"
                        >
                          <Volume2 className="w-3.5 h-3.5" />
                          <span>{playingAudioUrl === matchedVoice.preview_url ? 'Durdur' : 'Dinle'}</span>
                        </button>
                      );
                    }
                    return null;
                  })()}
                </div>
                <p className="text-[11px] text-gray-400 mt-1">
                  Karakterin diyalog satırları Blender render işlemi öncesinde ElevenLabs ile bu ses profili üzerinden sentezlenir.
                </p>
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
