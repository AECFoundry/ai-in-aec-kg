import { useRef, useCallback, useEffect } from "react";
import { useAppStore } from "../stores/appStore";
import { useChat } from "./useChat";
import { fetchTTS, fetchVoiceCapabilities } from "../lib/api";

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

export function useVoice() {
  const voiceState = useAppStore((s) => s.voiceState);
  const setVoiceState = useAppStore((s) => s.setVoiceState);
  const ttsAvailable = useAppStore((s) => s.ttsAvailable);
  const setTtsAvailable = useAppStore((s) => s.setTtsAvailable);
  const { sendMessage } = useChat();

  const recognitionRef = useRef<any>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pendingTTSRef = useRef(false);
  // Stable ref to speakText so the subscribe closure always calls the latest version
  const speakTextRef = useRef<(text: string) => Promise<void>>(async () => {});

  useEffect(() => {
    fetchVoiceCapabilities()
      .then((caps) => setTtsAvailable(caps.tts_available))
      .catch(() => setTtsAvailable(false));
  }, [setTtsAvailable]);

  useEffect(() => {
    const unsub = useAppStore.subscribe((state) => {
      if (!pendingTTSRef.current) return;

      const msgs = state.messages;
      const lastMsg = msgs[msgs.length - 1];
      if (!lastMsg || lastMsg.role !== "assistant") return;

      if (lastMsg.isStreaming) return;

      pendingTTSRef.current = false;

      if (state.ttsAvailable && lastMsg.content) {
        speakTextRef.current(lastMsg.content);
      } else {
        setVoiceState("idle");
      }
    });
    return unsub;
  }, [setVoiceState]);

  const speakText = useCallback(async (text: string) => {
    const token = useAppStore.getState().token;
    if (!token) {
      setVoiceState("idle");
      return;
    }

    setVoiceState("speaking");
    try {
      const blob = await fetchTTS(text, token);
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

      await audio.play();
    } catch {
      setVoiceState("idle");
    }
  }, [setVoiceState]);

  // Keep the ref in sync with the latest callback
  speakTextRef.current = speakText;

  const stopSpeaking = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setVoiceState("idle");
  }, [setVoiceState]);

  const startListening = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

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
        pendingTTSRef.current = true;
        sendMessage(transcript.trim());
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
  }, [sendMessage, setVoiceState]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setVoiceState("idle");
  }, [setVoiceState]);

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
