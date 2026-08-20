"use client";

import React, { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Send, Sparkles, Volume2, Command, Zap } from "lucide-react";

export interface SpeechControlProps {
  onProcessCommand: (instructionText: string) => void;
  isProcessing: boolean;
  isTtsEnabled: boolean;
  speakText: (text: string) => void;
}

export function SpeechControl({
  onProcessCommand,
  isProcessing,
  isTtsEnabled,
  speakText,
}: SpeechControlProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [inputText, setInputText] = useState("");
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = "de-DE";

        recognition.onresult = (event: any) => {
          let current = "";
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            current += event.results[i][0].transcript;
          }
          setTranscript(current);
          setInputText(current);
        };

        recognition.onend = () => {
          setIsListening(false);
        };

        recognition.onerror = () => {
          setIsListening(false);
        };

        recognitionRef.current = recognition;
      }
    }
  }, []);

  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
    } else {
      if (recognitionRef.current) {
        setTranscript("");
        setInputText("");
        try {
          recognitionRef.current.start();
          setIsListening(true);
        } catch (e) {
          console.error(e);
        }
      } else {
        alert("Web Speech API wird in diesem Browser nicht unterstützt. Bitte benutze das Texteingabefeld.");
      }
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const finalQuery = inputText || transcript;
    if (!finalQuery.trim() || isProcessing) return;

    onProcessCommand(finalQuery.trim());
  };

  const handleQuickCommand = (cmd: string) => {
    setInputText(cmd);
    onProcessCommand(cmd);
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Mic className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
              Sprachkanal / Voice Command Interface
            </h3>
            <p className="text-[11px] text-slate-400">
              {isListening ? "Höre zu... Sprich jetzt deinen Befehl." : "Drücke das Mikrofon oder wähle einen Befehl."}
            </p>
          </div>
        </div>

        {isListening && (
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
            <span className="text-xs font-mono text-red-400 font-semibold">REC</span>
          </div>
        )}
      </div>

      {/* Voice Wave Visualizer */}
      {isListening && (
        <div className="flex items-center justify-center gap-1.5 py-2 mb-3 bg-slate-950/80 rounded-xl border border-red-900/40">
          <div className="w-1.5 bg-red-500 rounded-full animate-[bounce_0.6s_infinite_100ms] h-6"></div>
          <div className="w-1.5 bg-red-500 rounded-full animate-[bounce_0.6s_infinite_200ms] h-9"></div>
          <div className="w-1.5 bg-red-500 rounded-full animate-[bounce_0.6s_infinite_300ms] h-4"></div>
          <div className="w-1.5 bg-red-500 rounded-full animate-[bounce_0.6s_infinite_150ms] h-8"></div>
          <div className="w-1.5 bg-red-500 rounded-full animate-[bounce_0.6s_infinite_250ms] h-5"></div>
          <span className="text-xs font-mono text-slate-300 ml-2">Liquid STT Active</span>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <button
          type="button"
          onClick={toggleListening}
          className={`p-3 rounded-xl border transition shadow-md flex items-center justify-center ${
            isListening
              ? "bg-red-600 border-red-500 text-white animate-pulse"
              : "bg-indigo-600 hover:bg-indigo-500 border-indigo-500 text-white"
          }`}
          title={isListening ? "Aufnahme stoppen" : "Spracheingabe starten"}
        >
          {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder='z.B. "Der Bereich hier gefällt mir nicht" oder "Nimm Vorschlag B"...'
          className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          disabled={isProcessing}
        />

        <button
          type="submit"
          disabled={!inputText.trim() || isProcessing}
          className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium text-sm flex items-center gap-2 disabled:opacity-40 shadow-lg"
        >
          {isProcessing ? (
            <Sparkles className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <span>Senden</span> <Send className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      {/* Preset Quick Chips */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
        <span className="text-[10px] font-mono text-slate-500 uppercase flex items-center gap-1">
          <Zap className="w-3 h-3 text-yellow-400" /> Schnellauswahl:
        </span>
        <button
          onClick={() => handleQuickCommand("Der Bereich hier gefällt mir nicht.")}
          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/80 transition text-[11px]"
        >
          "Der Bereich hier gefällt mir nicht"
        </button>
        <button
          onClick={() => handleQuickCommand("Mach die Navigation kompakter und dunkler.")}
          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/80 transition text-[11px]"
        >
          "Mach den Header kompakter"
        </button>
        <button
          onClick={() => handleQuickCommand("Nimm B")}
          className="px-2.5 py-1 rounded-lg bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-800/80 transition text-[11px] font-bold"
        >
          "Nimm B"
        </button>
      </div>
    </div>
  );
}
