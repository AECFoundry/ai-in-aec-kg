import { useRef, useCallback, useEffect } from "react";
import { useAppStore } from "../stores/appStore";
import { useChat } from "./useChat";
import { fetchTTS, fetchVoiceCapabilities } from "../lib/api";

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

// ---------------------------------------------------------------------------
// Sentence boundary detection
// ---------------------------------------------------------------------------

const ABBREV_RE = /(?:Dr|Mr|Mrs|Ms|Prof|Inc|Ltd|etc|e\.g|i\.e|vs)\.\s*$/i;

function extractCompleteSentences(buffer: string): {
  sentences: string[];
  remainder: string;
} {
  const sentences: string[] = [];
  let lastIndex = 0;

  // Match .!? followed by whitespace + uppercase letter or quote
  const pattern = /[.!?](?:\s+(?=[A-Z"'"]))/g;
  let match;
  while ((match = pattern.exec(buffer)) !== null) {
    const candidate = buffer.slice(lastIndex, match.index + 1).trim();
    // Skip abbreviations and very short fragments
    if (candidate.length >= 15 && !ABBREV_RE.test(candidate)) {
      sentences.push(candidate);
      lastIndex = match.index + match[0].length;
    }
  }

  return { sentences, remainder: buffer.slice(lastIndex) };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const MAX_CONCURRENT_TTS = 3;

export function useVoice() {
  const voiceState = useAppStore((s) => s.voiceState);
  const setVoiceState = useAppStore((s) => s.setVoiceState);
  const ttsAvailable = useAppStore((s) => s.ttsAvailable);
  const setTtsAvailable = useAppStore((s) => s.setTtsAvailable);
  const setPendingTTS = useAppStore((s) => s.setPendingTTS);
  const { sendMessage } = useChat();

  const recognitionRef = useRef<any>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Sentence-level TTS pipelining refs
  const sentenceBufferRef = useRef("");
  const processedLenRef = useRef(0); // how much of spokenAnswer we've consumed
  const sentenceIndexRef = useRef(0);
  const ttsResultsRef = useRef<Map<number, Blob>>(new Map());
  const nextPlayIndexRef = useRef(0);
  const isPlayingRef = useRef(false);
  const inFlightRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const allSentencesDoneRef = useRef(false);
  const pipelineActiveRef = useRef(false);

  useEffect(() => {
    fetchVoiceCapabilities()
      .then((caps) => setTtsAvailable(caps.tts_available))
      .catch(() => setTtsAvailable(false));
  }, [setTtsAvailable]);

  // --- Ordered audio playback queue ---
  const drainQueue = useCallback(() => {
    if (isPlayingRef.current) return;
    const idx = nextPlayIndexRef.current;
    const blob = ttsResultsRef.current.get(idx);
    if (!blob) {
      // Nothing ready — if all sentences are done and nothing left, go idle
      if (allSentencesDoneRef.current && ttsResultsRef.current.size === 0) {
        pipelineActiveRef.current = false;
        setVoiceState("idle");
      }
      return;
    }

    ttsResultsRef.current.delete(idx);
    nextPlayIndexRef.current = idx + 1;
    isPlayingRef.current = true;
    setVoiceState("speaking");

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioRef.current = audio;

    const onDone = () => {
      URL.revokeObjectURL(url);
      audioRef.current = null;
      isPlayingRef.current = false;
      drainQueue();
    };

    audio.onended = onDone;
    audio.onerror = onDone;
    audio.play().catch(onDone);
  }, [setVoiceState]);

  // --- Fire TTS for a single sentence ---
  const fireTTS = useCallback(
    (text: string, index: number) => {
      const controller = abortControllerRef.current;
      const signal = controller?.signal;

      inFlightRef.current += 1;
      fetchTTS(text, signal)
        .then((blob) => {
          ttsResultsRef.current.set(index, blob);
          drainQueue();
        })
        .catch(() => {
          // On failure (or abort), mark as done so playback doesn't stall
          // by not inserting — drainQueue will skip via nextPlayIndex
          // We still need to advance if this was the next expected index
          if (nextPlayIndexRef.current === index) {
            nextPlayIndexRef.current = index + 1;
            drainQueue();
          }
        })
        .finally(() => {
          inFlightRef.current -= 1;
        });
    },
    [drainQueue],
  );

  // --- Process new spoken tokens into sentences and dispatch TTS ---
  const processSpokenTokens = useCallback(
    (spokenAnswer: string, isFinal: boolean) => {
      // Feed only the new portion into the buffer
      const newText = spokenAnswer.slice(processedLenRef.current);
      if (!newText && !isFinal) return;
      processedLenRef.current = spokenAnswer.length;
      sentenceBufferRef.current += newText;

      // Extract complete sentences
      const { sentences, remainder } = extractCompleteSentences(
        sentenceBufferRef.current,
      );

      for (const sentence of sentences) {
        const idx = sentenceIndexRef.current++;
        if (inFlightRef.current < MAX_CONCURRENT_TTS) {
          fireTTS(sentence, idx);
        }
      }
      sentenceBufferRef.current = remainder;

      // On final flush, send any remaining text as the last TTS chunk
      if (isFinal && remainder.trim().length > 0) {
        const idx = sentenceIndexRef.current++;
        fireTTS(remainder.trim(), idx);
        sentenceBufferRef.current = "";
        allSentencesDoneRef.current = true;
      } else if (isFinal) {
        allSentencesDoneRef.current = true;
        // If nothing is playing and nothing in queue, go idle
        if (!isPlayingRef.current && ttsResultsRef.current.size === 0) {
          pipelineActiveRef.current = false;
          setVoiceState("idle");
        }
      }
    },
    [fireTTS, setVoiceState],
  );

  // --- Reset pipeline state ---
  const resetPipeline = useCallback(() => {
    sentenceBufferRef.current = "";
    processedLenRef.current = 0;
    sentenceIndexRef.current = 0;
    ttsResultsRef.current.clear();
    nextPlayIndexRef.current = 0;
    isPlayingRef.current = false;
    inFlightRef.current = 0;
    allSentencesDoneRef.current = false;
    pipelineActiveRef.current = false;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = null;
  }, []);

  // --- Store subscription: watch for spoken tokens and stream end ---
  useEffect(() => {
    let prevSpokenLen = 0;
    let prevIsStreaming = true;

    const unsub = useAppStore.subscribe((state) => {
      if (!state.pendingTTS) return;
      if (!state.ttsAvailable) return;

      const msgs = state.messages;
      const lastMsg = msgs[msgs.length - 1];
      if (!lastMsg || lastMsg.role !== "assistant") return;

      const spokenAnswer = lastMsg.spokenAnswer || "";
      const isStreaming = lastMsg.isStreaming ?? false;

      // Initialize pipeline on first spoken token
      if (spokenAnswer.length > 0 && !pipelineActiveRef.current) {
        pipelineActiveRef.current = true;
        abortControllerRef.current = new AbortController();
      }

      // Process new spoken tokens as they arrive
      if (spokenAnswer.length > prevSpokenLen && pipelineActiveRef.current) {
        processSpokenTokens(spokenAnswer, false);
      }

      // Detect stream end: isStreaming went from true to false
      if (prevIsStreaming && !isStreaming && pipelineActiveRef.current) {
        useAppStore.getState().setPendingTTS(false);
        processSpokenTokens(spokenAnswer, true);
      }

      // Handle case where stream ends with no spoken tokens at all
      if (prevIsStreaming && !isStreaming && !pipelineActiveRef.current) {
        useAppStore.getState().setPendingTTS(false);
        setVoiceState("idle");
      }

      prevSpokenLen = spokenAnswer.length;
      prevIsStreaming = isStreaming;
    });
    return unsub;
  }, [setVoiceState, setPendingTTS, processSpokenTokens]);

  const stopSpeaking = useCallback(() => {
    // Stop current audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    // Abort in-flight TTS and reset pipeline
    resetPipeline();
    setPendingTTS(false);
    setVoiceState("idle");
  }, [setVoiceState, setPendingTTS, resetPipeline]);

  const startListening = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    resetPipeline();

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech recognition not supported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0]?.[0]?.transcript;
      if (transcript?.trim()) {
        setVoiceState("processing");
        sendMessage(transcript.trim(), { voiceInitiated: true });
      } else {
        setVoiceState("idle");
      }
    };

    recognition.onerror = () => {
      setVoiceState("idle");
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      const current = useAppStore.getState().voiceState;
      if (current === "listening") {
        setVoiceState("idle");
      }
    };

    recognitionRef.current = recognition;
    setVoiceState("listening");
    recognition.start();
  }, [sendMessage, setVoiceState, resetPipeline]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setVoiceState("idle");
  }, [setVoiceState]);

  const speakText = useCallback(
    async (text: string) => {
      setVoiceState("speaking");
      try {
        const blob = await fetchTTS(text);
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          URL.revokeObjectURL(url);
          audioRef.current = null;
          setVoiceState("idle");
        };
        audio.onerror = () => {
          URL.revokeObjectURL(url);
          audioRef.current = null;
          setVoiceState("idle");
        };

        audio.play().catch(() => {
          URL.revokeObjectURL(url);
          audioRef.current = null;
          setVoiceState("idle");
        });
      } catch {
        setVoiceState("idle");
      }
    },
    [setVoiceState],
  );

  const toggle = useCallback(() => {
    switch (voiceState) {
      case "idle":
        startListening();
        break;
      case "listening":
        stopListening();
        break;
      case "speaking":
        stopSpeaking();
        break;
      case "processing":
        break;
    }
  }, [voiceState, startListening, stopListening, stopSpeaking]);

  const isSupported =
    typeof window !== "undefined" &&
    (!!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition);

  return {
    voiceState,
    ttsAvailable,
    isSupported,
    toggle,
    startListening,
    stopListening,
    stopSpeaking,
    speakText,
  };
}
