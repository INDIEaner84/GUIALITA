"use client";

import React, { useState } from "react";
import { Monitor, MousePointer, Keyboard, Terminal, ExternalLink, Play, CheckCircle2, ShieldAlert } from "lucide-react";

export function DesktopControlPanel() {
  const [selectedApp, setSelectedApp] = useState("Chromium");
  const [actionType, setActionType] = useState("mouse_click");
  const [coords, setCoords] = useState({ x: 480, y: 320 });
  const [actionsLog, setActionsLog] = useState<any[]>([
    {
      id: "desk_1",
      app: "Chromium",
      type: "mouse_click",
      desc: "Navigated to http://localhost:3000 in Chromium browser window.",
      status: "completed",
      time: "10:14:02",
    },
    {
      id: "desk_2",
      app: "VS Code",
      type: "key_press",
      desc: "Triggered 'Ctrl+Save' in src/components/live/LiveHero.tsx.",
      status: "completed",
      time: "10:14:28",
    },
  ]);
  const [isExecuting, setIsExecuting] = useState(false);

  const handleRunAction = async () => {
    setIsExecuting(true);
    try {
      const res = await fetch("/api/desktop/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actionType,
          coordinates: coords,
          targetApp: selectedApp,
          description: `Executed ${actionType} on ${selectedApp} at (${coords.x}, ${coords.y})`,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setActionsLog((prev) => [
          {
            id: data.action.id,
            app: selectedApp,
            type: actionType,
            desc: data.action.description,
            status: "completed",
            time: new Date().toLocaleTimeString(),
          },
          ...prev,
        ]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
            <Monitor className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              Phase 7 — Desktop Automation Agent
              <span className="text-[10px] bg-purple-950 text-purple-300 px-2 py-0.5 rounded border border-purple-800">
                Modular Module
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Steuerung von Maus, Tastatur und Fenstern außerhalb des rein isolierten Browser DOMs.
            </p>
          </div>
        </div>

        <div className="text-right text-xs">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-950 text-emerald-400 border border-emerald-900">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span> Host OS Bridge Ready
          </span>
        </div>
      </div>

      {/* Control Sandbox */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* App Switcher */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <ExternalLink className="w-3.5 h-3.5 text-indigo-400" /> Zielanwendung
          </label>
          <div className="space-y-1.5">
            {["Chromium", "VS Code", "Terminal / Bash", "Liquid Desktop UI"].map((app) => (
              <button
                key={app}
                onClick={() => setSelectedApp(app)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition flex items-center justify-between ${
                  selectedApp === app
                    ? "bg-purple-950 text-purple-200 border border-purple-700 shadow"
                    : "bg-slate-900 text-slate-400 hover:text-white"
                }`}
              >
                <span>{app}</span>
                {selectedApp === app && <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />}
              </button>
            ))}
          </div>
        </div>

        {/* Action Type & Coordinates */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <MousePointer className="w-3.5 h-3.5 text-indigo-400" /> Aktion & Koordinaten
          </label>

          <div className="space-y-2 text-xs">
            <div>
              <span className="text-slate-400 block mb-1">Aktionstyp:</span>
              <select
                value={actionType}
                onChange={(e) => setActionType(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 text-white rounded-lg p-2 focus:ring-2 focus:ring-purple-500"
              >
                <option value="mouse_click">Mouse Left Click</option>
                <option value="mouse_double_click">Mouse Double Click</option>
                <option value="key_press">Key Press (Ctrl+S)</option>
                <option value="launch_app">Launch Application</option>
                <option value="screenshot">Capture Screen</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <div>
                <span className="text-slate-400 block mb-1">X Koordinate:</span>
                <input
                  type="number"
                  value={coords.x}
                  onChange={(e) => setCoords({ ...coords, x: parseInt(e.target.value) || 0 })}
                  className="w-full bg-slate-900 border border-slate-800 text-white rounded-lg p-2"
                />
              </div>
              <div>
                <span className="text-slate-400 block mb-1">Y Koordinate:</span>
                <input
                  type="number"
                  value={coords.y}
                  onChange={(e) => setCoords({ ...coords, y: parseInt(e.target.value) || 0 })}
                  className="w-full bg-slate-900 border border-slate-800 text-white rounded-lg p-2"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleRunAction}
            disabled={isExecuting}
            className="w-full mt-2 py-2 px-3 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow"
          >
            <Play className="w-3.5 h-3.5" /> Desktop Aktion Ausführen
          </button>
        </div>

        {/* Security Fence Notice */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-amber-400 text-xs font-bold mb-2">
              <ShieldAlert className="w-4 h-4" /> Sicherheitsgrenzen (Safety Policy)
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Der Agent darf nicht ohne Bestätigung Dateien außerhalb des Projekts löschen, externe Accounts bedienen oder destruktive Systembefehle ausführen.
            </p>
          </div>

          <div className="mt-4 p-2.5 bg-slate-900 rounded-lg text-[10px] font-mono text-slate-400 border border-slate-800">
            Status: Sandboxed local automation session
          </div>
        </div>
      </div>

      {/* Execution Log */}
      <div className="space-y-2">
        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
          <Terminal className="w-3.5 h-3.5 text-purple-400" /> Execution Log Stream
        </h4>
        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-xs max-h-40 overflow-y-auto space-y-1.5">
          {actionsLog.map((log) => (
            <div key={log.id} className="flex items-center justify-between text-[11px] text-slate-300 border-b border-slate-900 pb-1">
              <div className="flex items-center gap-2">
                <span className="text-purple-400 font-bold">[{log.app}]</span>
                <span>{log.desc}</span>
              </div>
              <span className="text-slate-500 text-[10px]">{log.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
