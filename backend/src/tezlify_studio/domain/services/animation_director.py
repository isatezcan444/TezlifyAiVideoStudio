"""Turn a SceneGraph into an AnimationPlan.

This is the piece that decides *what a character does*, so it is the answer to
the brief's "hareketler hikâyeden üretilmeli" requirement. It reads the dialogue
text, the speaker, the listener, the placement, the expression and the scene
length, and schedules clips from `animation_clips`.

Two deliberate constraints:

* Nothing here is random. Every choice is a function of the script and of a
  character's `CharacterAnimationProfile`, which is itself derived from the
  character id. Re-rendering the same project reproduces the same performance.
* Turkish is matched on lowercase, diacritic-folded text so that "Merhaba",
  "MERHABA" and "merhaba" behave the same, and so that the dotted/undotted i
  pair does not split a word across two forms.

Stdlib-only, because `render_worker.py` imports it inside Blender.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from tezlify_studio.domain.services import animation_clips
from tezlify_studio.domain.value_objects.animation_plan import (
    PRIORITY_ATTENTION,
    PRIORITY_BASE,
    PRIORITY_EMOTION,
    PRIORITY_GESTURE,
    PRIORITY_IDLE,
    AnimationClipInstance,
    CharacterAnimationProfile,
    FacialExpression,
    Gesture,
    SceneAnimationPlan,
    Shot,
    ShotPlan,
)

# Turkish case folding. The I pair is the trap and it is easy to invert:
# 'İ' (dotted capital) lowers to 'i', while 'I' (dotless capital) lowers to 'ı'.
# Getting this backwards turns "NASILSIN" into "nasilsin" and the word then
# matches none of the needles below.
_LOWER_MAP = str.maketrans("İIĞÜŞÖÇ", "iığüşöç")

# Ordered so the more specific pattern wins when both match.
_INTENT_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("laugh", ("kahkaha", "haha", "hihi", "güldür", "komik", "gülüyorum", "güldü")),
    ("greeting", ("merhaba", "selam", "sana", "günaydın", "iyi akşamlar",
                  "iyi geceler", "hoş geldin", "nasılsın", "naber")),
    ("surprised", ("gerçekten mi", "gercekten mi", "vay", "inanamıyorum",
                   "ciddi misin", "yok artık", "şaşkın", "şaşırdım", "aa,")),
    ("question", ("mı", "mi", "mu", "mü", "nedir", "neden", "niye", "nasıl",
                  "kim", "hangi", "ne zaman", "nerede", "kaç")),
    ("agree", ("evet", "doğru", "haklısın", "katılıyorum", "tamam", "olur", "bence de")),
    ("refuse", ("hayır", "olmaz", "katılmıyorum", "istemiyorum", "değil", "yok")),
    ("sad", ("üzgün", "üzüldüm", "keşke", "ağladım", "kötü hissed", "yalnız",
             "özledim", "pişman")),
    ("angry", ("kızgın", "sinir", "öfke", "yeter artık", "bezdim", "kavga")),
    ("embarrassed", ("özür", "kusura bakma", "utanç", "mahcup", "hata yaptım",
                     "pardon", "gaf")),
    ("thinking", ("sanırım", "hmm", "düşünüyorum", "bir düşüneyim", "acaba",
                  "hatırlamıyorum", "galiba")),
    ("confused", ("anlamadım", "nasıl yani", "şaşkın", "karıştı", "ne alaka",
                  "bilmiyorum", "olmaz öyle")),
    ("curious", ("merak", "söyle bakalım", "göster", "anlat", "hikâye", "hikaye",
                 "okudun mu", "denedin mi")),
    ("explain", ("çünkü", "yani", "şöyle", "bunu yap", "bak", "göster",
                 "anlat", "önce", "sonra", "mesela")),
    ("point", ("şu", "buraya", "oraya", "şuna", "buna", "onunla")),
    ("happy", ("güzel", "harika", "mükemmel", "süper", "mutlu", "sevindim",
               "bayılıyorum", "keyif", "seviyorum", "çok iyi")),
)

_EMOTION_CLIP = {
    "happy": "happy",
    "sad": "sad",
    "surprised": "surprised",
    "confused": "confused",
    "angry": "angry",
    "curious": "curious",
    "embarrassed": "embarrassed",
    "thinking": "thinking",
    "laugh": "laughing",
}

# Expression enum values from CharacterExpression, mapped to a mood clip.
_EXPRESSION_MOOD = {
    "cheerful": "happy",
    "happy": "happy",
    "excited": "happy",
    "sad": "sad",
    "angry": "angry",
    "surprised": "surprised",
    "neutral": "",
}

_SPEECH_CLIP = {
    "high": "talk_excited",
    "calm": "talk_calm",
    "serious": "talk_serious",
}


def normalize(text: str) -> str:
    return (text or "").translate(_LOWER_MAP).lower()


def detect_intents(text: str) -> List[str]:
    """All intents present in one line, most specific first."""
    folded = normalize(text)
    found: List[str] = []
    for intent, needles in _INTENT_RULES:
        if any(needle in folded for needle in needles):
            found.append(intent)
    if "?" in (text or "") and "question" not in found:
        found.append("question")
    return found


def _speech_style(intents: Sequence[str], energy: float) -> str:
    if "explain" in intents or "curious" in intents:
        return "high" if energy >= 1.05 else "calm"
    if "sad" in intents or "thinking" in intents or "embarrassed" in intents:
        return "serious"
    if "happy" in intents or "surprised" in intents or "laugh" in intents:
        return "high"
    if "angry" in intents:
        return "serious"
    return "calm"


# Which body resources a non-additive clip owns, derived from the channels it
# writes. Two clips only conflict when they drive the same joints: a head turn
# does not prevent a hand beat, and treating them as one resource would drop
# gestures for no reason.
def _resources(clip_name: str) -> frozenset:
    clip = animation_clips.CLIPS.get(clip_name)
    return clip.resources if clip else frozenset({"head", "arms", "body"})


class _Reservation:
    """Occupied time per character per body resource.

    The plan validator rejects same-priority overlaps because the later keyframe
    would silently overwrite the earlier one and the gesture would disappear.
    Reserving up front means the most meaningful gesture of a line always wins:
    a greeting or a question is placed first, the generic emphasis beats fill
    whatever is left.
    """

    def __init__(self) -> None:
        self._busy: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}

    def place(self, character_id: str, clip_name: str, start: float, length: float,
              limit: float, priority: int = 0) -> Optional[Tuple[float, float]]:
        # Only the same priority is a conflict: the validator allows a higher
        # priority clip to override a lower one on the channels they share.
        resources = _resources(clip_name) or {"all"}
        spans = [self._busy.setdefault((character_id, resource, priority), [])
                 for resource in resources]
        for candidate in (start, start + length * 0.35, max(0.0, start - length * 0.35)):
            end = min(limit, candidate + length)
            if end - candidate < 0.35:
                continue
            if all(end <= other_start or candidate >= other_end
                   for busy in spans for other_start, other_end in busy):
                for busy in spans:
                    busy.append((candidate, end))
                return candidate, end
        return None


def _gesture_sequence(
    intents: Sequence[str],
    window: float,
    profile: CharacterAnimationProfile,
    speaker_name: str,
) -> List[Tuple[str, float, float, str]]:
    """Gestures to place inside one dialogue, with their offsets and a reason.

    A greeting or a question owns the start of the line because that is where a
    human does it; explanatory beats are spread over the middle; a closing beat
    lands near the end so the line does not stop dead.
    """
    out: List[Tuple[str, float, float, str]] = []
    if window <= 0:
        return out

    def add(name: str, at: float, length: float, reason: str) -> None:
        from tezlify_studio.domain.services import animation_clips

        clip = animation_clips.CLIPS.get(name)
        if clip is None:
            return
        span = min(length, clip.duration, max(window, 0.2))
        start = max(0.0, min(at, window - span))
        out.append((name, start, start + span, reason))

    if "greeting" in intents:
        add("greeting", 0.15, 1.8, "opening greeting in the line")
    if "question" in intents:
        add("ask_question", 0.30 if "greeting" not in intents else window * 0.55,
            1.9, "questioning intonation")
    if "explain" in intents or "curious" in intents:
        add("explain_with_hands", window * 0.25, 2.4, "explanatory content")
    if "point" in intents:
        add("pointing", window * 0.45, 1.6, "deictic word (şu/bu/oraya)")
    if "agree" in intents:
        add("nodding", window * 0.35, 1.1, "explicit agreement")
    if "refuse" in intents:
        add("shaking_head", window * 0.35, 1.3, "explicit refusal")
    if "laugh" in intents:
        add("laughing", window * 0.40, 1.6, "laughter in the line")
    if "surprised" in intents:
        # The *speaker* is startled by their own news, not reacting to a
        # partner line; react_to_partner belongs to the listener.
        add("surprised", 0.10, 1.2, "surprise in the line")
    if "shrug" in intents:
        add("shrugging", window * 0.5, 1.2, "uncertainty")

    # A plain statement still needs beats, otherwise it looks frozen. How many
    # depends on the character's own gesture rate, not on a fixed count.
    beats = max(1, int(round(window / 2.4 * profile.gesture_rate)))
    if "greeting" not in intents and "question" not in intents:
        beats = max(beats, 1)
    lead = "hand_gesture"
    for index in range(beats):
        if len(out) >= max(1, min(4, int(window // 1.8))):
            break
        at = window * (0.20 + 0.62 * index / max(1, beats))
        add(lead, at, 1.4, f"emphasis beat {index + 1} of a {window:.1f}s line")
    return out


def _listener_behaviour(
    character_id: str,
    window: float,
    profile: CharacterAnimationProfile,
    speaker_id: str,
    speaker_intents: Sequence[str],
) -> List[Tuple[str, float, float, str]]:
    """What the non-speaking character does while the other one talks."""
    out: List[Tuple[str, float, float, str]] = [
        ("listen_attentive", 0.0, min(window, 2.2), f"attending to {speaker_id}"),
    ]
    # Nods are the visible proof that a listener is not a statue. Their count
    # follows the listener's own gesture rate, so characters disagree slightly.
    nods = max(1, int(round(window / 3.2 * profile.gesture_rate)))
    for index in range(nods):
        out.append(("nodding", window * (0.25 + 0.5 * index / max(1, nods)), 1.1,
                    f"agreement nod {index + 1} while listening"))
    if "laugh" in speaker_intents:
        out.append(("laughing", window * 0.55, 1.6, "laughing along with the speaker"))
    elif "question" in speaker_intents:
        out.append(("thinking", window * 0.45, 2.0, "considering the question asked"))
    elif "surprised" in speaker_intents:
        out.append(("surprised", window * 0.50, 1.1, "reacting to surprising news"))
    return out


def _shots_for_scene(
    duration: float,
    dialogues: Sequence[Tuple[str, float, float]],
    characters: Sequence[str],
) -> ShotPlan:
    """A shot plan that follows the story instead of wandering.

    Close-ups are only taken for lines long enough to earn a cut, and a reaction
    beat is inserted right after a speaker stops - that is the moment an
    audience wants to see the listener's face.
    """
    shots: List[Shot] = []
    if duration <= 0 or not characters:
        return ShotPlan(scene_id="", shots=())

    cursor = 0.0
    establishing = min(1.4, duration * 0.25)
    shots.append(Shot("establishing", 0.0, establishing, None))
    cursor = establishing

    for speaker, start, end in dialogues:
        if start > cursor:
            shots.append(Shot("two_shot", cursor, min(start, duration), None))
            cursor = start
        length = end - start
        if length >= 3.2 and len(characters) > 1:
            mid = start + length * 0.45
            shots.append(Shot("two_shot", start, mid, speaker))
            shots.append(Shot("speaker_close_up", mid, end, speaker))
        else:
            shots.append(Shot("two_shot", start, end, speaker))
        cursor = end
        reaction_end = min(duration, end + 0.9)
        if reaction_end > end:
            listener = next((c for c in characters if c != speaker), None)
            shots.append(Shot("listener_reaction", end, reaction_end, listener))
            cursor = reaction_end

    if cursor < duration:
        shots.append(Shot("two_shot", cursor, duration, None))

    merged: List[Shot] = []
    for shot in shots:
        if shot.end - shot.start < 0.35 and merged:
            merged[-1] = Shot(merged[-1].kind, merged[-1].start, shot.end,
                              merged[-1].focus_character_id)
            continue
        merged.append(shot)
    return ShotPlan(scene_id="", shots=tuple(merged))


def plan_scene(
    *,
    scene_id: str,
    duration: float,
    characters: Sequence[str],
    dialogues: Sequence[Dict[str, object]],
    expressions: Optional[Dict[str, str]] = None,
    placements: Optional[Dict[str, Sequence[float]]] = None,
    profiles: Optional[Dict[str, CharacterAnimationProfile]] = None,
) -> SceneAnimationPlan:
    """Build one scene's plan from its script.

    `dialogues` entries need `character_id`, `start_time`, `end_time` and `text`.
    """
    expressions = expressions or {}
    placements = placements or {}
    profiles = profiles or {c: CharacterAnimationProfile.for_character(c) for c in characters}

    clips: List[AnimationClipInstance] = []
    gestures: List[Gesture] = []
    face: List[FacialExpression] = []
    reserved = _Reservation()
    dropped: List[str] = []

    def schedule(character_id: str, name: str, at: float, until: float, priority: int,
                 weight: float, reason: str, as_gesture: bool) -> None:
        """Place one clip, reserving time for clips that own their channels."""
        start = max(0.0, min(at, duration))
        end = min(duration, max(start + 0.05, until))
        if animation_clips.CLIPS[name].additive:
            clips.append(AnimationClipInstance(character_id, name, start, end,
                                               priority, weight, reason))
            if as_gesture:
                gestures.append(Gesture(character_id, name, start, end, reason))
            return
        placed = reserved.place(character_id, name, start, end - start, duration, priority)
        if placed is None:
            dropped.append(f"{character_id}:{name}@{start:.2f}")
            return
        clips.append(AnimationClipInstance(character_id, name, placed[0], placed[1],
                                           priority, weight, reason))
        if as_gesture:
            gestures.append(Gesture(character_id, name, placed[0], placed[1], reason))

    ordered = sorted(dialogues, key=lambda d: float(d["start_time"]))  # type: ignore[arg-type]
    windows = [(str(d["character_id"]), float(d["start_time"]), float(d["end_time"]),  # type: ignore[arg-type]
                str(d.get("text", "")))
               for d in ordered]

    # Everything that is not speech is filled with the character's own idle and
    # breathing layer, scheduled as one long instance rather than retriggered, so
    # a character never visibly restarts its loop.
    for character_id in characters:
        schedule(character_id, "breathing", 0.0, duration, PRIORITY_BASE, 1.0,
                 "continuous breath layer", False)
        schedule(character_id, "idle_natural", 0.0, duration, PRIORITY_IDLE, 1.0,
                 "continuous idle layer", False)

    for index, (speaker, start, end, text) in enumerate(windows):
        window = max(0.0, end - start)
        profile = profiles[speaker]
        intents = detect_intents(text)

        mood = _EXPRESSION_MOOD.get(str(expressions.get(speaker, "")).lower(), "")
        emotion = _EMOTION_CLIP.get(intents[0] if intents else "", mood)
        if emotion:
            schedule(speaker, emotion, start, start + window, PRIORITY_EMOTION, 0.9,
                     f"emotion from {'/'.join(intents[:2]) or 'expression'}", False)
            face.append(FacialExpression(speaker, emotion, start, end))

        style = _speech_style(intents, profile.energy)
        schedule(speaker, _SPEECH_CLIP[style], start, start + window, PRIORITY_BASE + 1, 1.0,
                 f"speech style '{style}' for line {index + 1}", False)

        if len(characters) > 1:
            attention = ("turn_toward_partner"
                         if index == 0 and placements.get(speaker) is not None
                         else "look_at_partner")
            schedule(speaker, attention, start, start + min(window, 1.2),
                     PRIORITY_ATTENTION, 1.0, "speaker addresses the partner", False)

        for name, offset, until, reason in _gesture_sequence(intents, window, profile, speaker):
            schedule(speaker, name, start + offset, start + until, PRIORITY_GESTURE, 1.0,
                     reason, True)

        listener = next((c for c in characters if c != speaker), None)
        if listener:
            lprofile = profiles[listener]
            for name, offset, until, reason in _listener_behaviour(
                    listener, window, lprofile, speaker, intents):
                priority = PRIORITY_GESTURE if name != "listen_attentive" else PRIORITY_BASE + 1
                schedule(listener, name, start + offset, start + until, priority, 0.85,
                         reason, name != "listen_attentive")

    # Gaps between lines get a glance so nobody stares at a wall for five seconds.
    gaps = []
    previous_end = 0.0
    for _, start, end, _ in windows:
        if start - previous_end > 1.6:
            gaps.append((previous_end, start))
        previous_end = max(previous_end, end)
    if duration - previous_end > 1.6:
        gaps.append((previous_end, duration))
    for gap_start, gap_end in gaps:
        for character_id in characters:
            schedule(character_id, "looking_around", gap_start,
                     min(gap_end, gap_start + 3.4), PRIORITY_ATTENTION, 0.6,
                     "filling a silence between lines", False)

    settle_start = max(0.0, duration - 1.4)
    for character_id in characters:
        schedule(character_id, "scene_end_settle", settle_start, duration, PRIORITY_IDLE, 1.0,
                 "settle instead of cutting to rest at the last frame", False)

    shot_plan = _shots_for_scene(
        duration,
        [(s, st, en) for s, st, en, _ in windows],
        list(characters),
    )

    return SceneAnimationPlan(scene_id=scene_id, duration=duration,
                              clips=tuple(clips), expressions=tuple(face),
                              gestures=tuple(gestures), dropped=tuple(dropped),
                              shot_plan=ShotPlan(scene_id, shot_plan.shots))


def _field(obj, name, default=None):
    """Read a field from either a pydantic model or its dict form.

    The application layer hands this module a `SceneGraph`, while
    `render_worker.py` inside Blender only has the manifest's plain dict - and
    Blender's Python cannot import pydantic at all.
    """
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def plan_scene_graph(scene_graph, profiles=None):
    """Convenience wrapper used by the application layer and the worker."""
    characters = [str(_field(c, "id")) for c in _field(scene_graph, "characters", [])]
    all_profiles = profiles or {c: CharacterAnimationProfile.for_character(c) for c in characters}
    plans: List[SceneAnimationPlan] = []
    for scene in _field(scene_graph, "scenes", []):
        placements_raw = _field(scene, "character_placements", [])
        placements = {str(_field(p, "character_id")): _field(p, "position", [0.0, 0.0, 0.0])
                      for p in placements_raw}
        expressions = {str(_field(p, "character_id")): str(_field(p, "expression", "neutral"))
                       for p in placements_raw}
        scene_characters = list(placements) or characters
        dialogues = [
            {
                "character_id": str(_field(d, "character_id")),
                "start_time": float(_field(d, "start_time", 0.0)),
                "end_time": float(_field(d, "end_time", 0.0)),
                "text": str(_field(d, "text", "")),
            }
            for d in _field(scene, "dialogues", [])
        ]
        plans.append(plan_scene(
            scene_id=str(_field(scene, "scene_id", "")),
            duration=float(_field(scene, "duration_seconds", 0.0)),
            characters=scene_characters,
            dialogues=dialogues,
            expressions=expressions,
            placements=placements,
            profiles=all_profiles,
        ))
    return plans, all_profiles
