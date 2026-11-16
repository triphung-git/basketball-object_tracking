"""Local Integrated Dashboard Server for Automatic Basketball Scoreboard (Task 12 & Task 05A).

Serves a lightweight, self-contained, offline-first dashboard providing:
  - Synchronized video playback with PTS timeline and event seek.
  - Live Box Score (Team summaries, Player lines, Invariant-preserving offsets).
  - 2D Court visualizer with real calibrated shot locations (zero fake coordinates).
  - Diagnostic Heatmap status handling (transparently reports unavailable reason when uncalibrated).
  - Event status inspection (auto_confirmed, candidate, unresolved, void, provisional).
  - Direct one-click exports of events_auto.jsonl, boxscore_auto.csv, and summary.json.
  - Robust HTTP Range streaming (proper 206 Partial Content and 416 Range Not Satisfiable).
  - Secure HTML escaping to prevent XSS from team/player metadata.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import html
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import socket
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

from basketball_scoreboard.boxscore import BoxScoreEngine, TeamBoxScore
from basketball_scoreboard.events import EventLedger, EventStatus, EventType, LedgerEventRecord
from basketball_scoreboard.identity import RosterConfig, RosterPlayer
from basketball_scoreboard.demo_bundle import summarize_run, verify_bundle_manifest


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Automatic Basketball Scoreboard &amp; Stats Dashboard</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --team-vie: #ef4444;
      --team-tga: #3b82f6;
      --badge-confirmed: #10b981;
      --badge-unresolved: #f59e0b;
      --badge-void: #64748b;
      --badge-provisional: #8b5cf6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.5;
      padding: 16px 24px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 12px;
    }
    h1 { font-size: 1.35rem; font-weight: 700; color: var(--text); }
    .status-bar { display: flex; gap: 10px; align-items: center; font-size: 0.85rem; color: var(--text-muted); flex-wrap: wrap; }
    .btn {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.82rem;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
    }
    .btn:hover { background: #273549; border-color: var(--accent); }
    .btn-primary { background: var(--accent); color: #0f172a; border-color: var(--accent); font-weight: 600; }
    .btn-primary:hover { background: var(--accent-hover); }

    .grid {
      display: grid;
      grid-template-columns: 1.35fr 1fr;
      gap: 20px;
    }
    .grid > * { min-width: 0; }
    .card { min-width: 0; overflow-wrap: break-word; }
    @media (max-width: 960px) {
      .grid { grid-template-columns: 1fr; }
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 20px;
    }
    .card-title {
      font-size: 0.95rem;
      font-weight: 600;
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }

    /* Video & Overlay */
    .video-container {
      position: relative;
      width: 100%;
      background: #000;
      border-radius: 6px;
      overflow: hidden;
      aspect-ratio: 16 / 9;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    video {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
    }
    .video-error-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.9);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 20px;
      text-align: center;
      color: #f87171;
      font-size: 0.9rem;
    }

    /* Timeline */
    .timeline-container {
      margin-top: 12px;
      position: relative;
      background: #0b0f19;
      height: 48px;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      overflow-x: auto;
      overflow-y: hidden;
    }
    .timeline-marker {
      position: absolute;
      top: 6px;
      height: 36px;
      width: 10px;
      border-radius: 3px;
      cursor: pointer;
      transition: transform 0.1s;
    }
    .timeline-marker:hover {
      transform: scaleY(1.2);
      z-index: 10;
    }
    .marker-shot { background: #10b981; }
    .marker-reb { background: #f59e0b; }
    .marker-ast { background: #8b5cf6; }
    .marker-to { background: #ef4444; }

    /* Box Score Tables */
    table {
      width: 100%;
      min-width: 480px;
      border-collapse: collapse;
      font-size: 0.82rem;
      text-align: right;
    }
    th, td {
      padding: 6px 8px;
      border-bottom: 1px solid var(--card-border);
    }
    th:first-child, td:first-child { text-align: left; }
    th:nth-child(2), td:nth-child(2) { text-align: left; }
    th {
      white-space: nowrap;
      color: var(--text-muted);
      font-weight: 600;
      background: #172033;
    }
    tr.team-header-row {
      font-weight: 700;
      background: #243047;
      color: var(--accent);
    }
    tr.team-unassigned-row {
      font-style: italic;
      color: var(--text-muted);
    }

    /* Event List */
    .event-list {
      max-height: 300px;
      overflow-y: auto;
      font-size: 0.82rem;
    }
    .event-item {
      padding: 8px 12px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      gap: 8px;
    }
    .event-item:hover {
      background: #273549;
    }
    .badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .badge-confirmed { background: var(--badge-confirmed); color: #022c22; }
    .badge-unresolved { background: var(--badge-unresolved); color: #451a03; }
    .badge-void { background: var(--badge-void); color: #f8fafc; }
    .badge-provisional { background: var(--badge-provisional); color: #f8fafc; }

    /* Court SVG */
    .court-container {
      width: 100%;
      background: #172033;
      border-radius: 6px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .info-banner {
      width: 100%;
      margin-top: 8px;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 0.78rem;
      background: #1e293b;
      border-left: 3px solid var(--accent);
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1 id="dashboardHeader">Automatic Basketball Stats Dashboard</h1>
      <span style="font-size: 0.8rem; color: var(--text-muted);">FIBA 3x3 Vietnam vs Tonga &bull; Integrated Studio</span>
    </div>
    <div class="status-bar">
      <span id="sessionStatus">Status: Ready</span>
      <span id="geometryBadge" class="badge badge-unresolved">Geometry: Uncalibrated</span>
      <a class="btn" href="/api/export/events" download="events_auto.jsonl">Export JSONL</a>
      <a class="btn" href="/api/export/boxscore" download="boxscore_auto.csv">Export CSV</a>
      <a class="btn" href="/api/export/summary" download="summary.json">Export Run JSON</a>
    </div>
  </header>

  <div class="grid">
    <!-- Left Column: Video, Timeline, and Court -->
    <div>
      <div class="card">
        <div class="card-title">
          <span>Game Footage &amp; Synchronized PTS</span>
          <span id="videoTime" style="font-size:0.85rem; color:var(--text-muted);">00:00.0</span>
        </div>
        <div class="video-container" id="videoBox">
          <video id="gameVideo" controls preload="metadata">
            <source src="/api/video" type="video/mp4">
            Your browser does not support the video tag.
          </video>
          <div id="videoErrorOverlay" class="video-error-overlay" style="display:none;">
            <strong>Video Source Unavailable</strong>
            <span style="font-size:0.8rem; margin-top:4px;">File not located on local disk. Interactive PTS timeline and statistics remain fully functional.</span>
          </div>
        </div>
        <div class="card-title" style="margin-top:16px; margin-bottom:4px;">
          <span style="font-size:0.85rem;">Temporal Event Spine (Click marker to seek video)</span>
        </div>
        <div class="timeline-container" id="timelineBar"></div>
      </div>

      <div class="card">
        <div class="card-title">
          <span>FIBA 3x3 Court Shot Heatmap</span>
          <span id="courtStatusBadge" style="font-size:0.8rem; color:var(--text-muted);">Calibrated Geometry</span>
        </div>
        <div class="court-container">
          <svg id="courtSvg" viewBox="0 0 500 400" width="100%" height="240" style="max-width:500px;">
            <!-- Court perimeter -->
            <rect x="20" y="20" width="460" height="360" fill="#1b253b" stroke="#475569" stroke-width="2"/>
            <!-- Half-court line & Key -->
            <rect x="180" y="20" width="140" height="180" fill="none" stroke="#475569" stroke-width="2"/>
            <!-- Free throw circle -->
            <path d="M 180 200 A 70 70 0 0 0 320 200" fill="none" stroke="#475569" stroke-width="2"/>
            <!-- 2-Point Arc (Radius 6.75m -> ~207px at 30.67px/m, centered on rim at 250, 68) -->
            <path d="M 43 20 L 43 68 A 207 207 0 0 0 457 68 L 457 20" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
            <!-- Basket Rim (at 0, 1.575m -> SVG 250, 68) -->
            <circle cx="250" cy="68" r="9" fill="none" stroke="#ef4444" stroke-width="3"/>
            <!-- Backboard (at 0, 1.20m -> SVG 250, 56) -->
            <line x1="215" y1="56" x2="285" y2="56" stroke="#f8fafc" stroke-width="4"/>
            <!-- Shot markers layer -->
            <g id="shotMarkersLayer"></g>
          </svg>
          <div id="heatmapDiagnosticBanner" class="info-banner" style="display:none;"></div>
        </div>
      </div>
    </div>

    <!-- Right Column: Box Score & Event Log -->
    <div>
      <div class="card">
        <div class="card-title">
          <span>Official FIBA Box Score</span>
          <span id="scoreHeader" style="font-weight:700; color:var(--accent);">Việt Nam 0 - 0 Tonga</span>
        </div>
        <div style="overflow-x: auto;">
          <table id="boxscoreTable">
            <thead>
              <tr>
                <th>Team / Player</th>
                <th>#</th>
                <th>PTS</th>
                <th>1PT</th>
                <th>2PT</th>
                <th>FT</th>
                <th>REB*</th>
                <th>AST*</th>
                <th>TO</th>
                <th>Unres</th>
              </tr>
            </thead>
            <tbody id="boxscoreBody">
              <tr><td colspan="10" style="text-align:center; padding:16px;">Loading Box Score...</td></tr>
            </tbody>
          </table>
        </div>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">
          * Note: REB/AST values marked with * reflect MVP development status; unmeasured stats are isolated and not claimed as verified zeros.
        </div>
      </div>

      <div class="card">
        <div class="card-title">
          <span>Adjudicated Event Ledger</span>
          <span id="eventCount" style="font-size:0.8rem; color:var(--text-muted);">0 events</span>
        </div>
        <div class="event-list" id="eventList">
          <div style="text-align:center; padding:16px; color:var(--text-muted);">No events recorded yet.</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const video = document.getElementById('gameVideo');
    const timeDisplay = document.getElementById('videoTime');
    const timelineBar = document.getElementById('timelineBar');
    const boxscoreBody = document.getElementById('boxscoreBody');
    const eventList = document.getElementById('eventList');
    const eventCount = document.getElementById('eventCount');
    const scoreHeader = document.getElementById('scoreHeader');
    const shotMarkersLayer = document.getElementById('shotMarkersLayer');
    const sessionStatus = document.getElementById('sessionStatus');
    const geometryBadge = document.getElementById('geometryBadge');
    const courtStatusBadge = document.getElementById('courtStatusBadge');
    const heatmapDiagnosticBanner = document.getElementById('heatmapDiagnosticBanner');
    const videoErrorOverlay = document.getElementById('videoErrorOverlay');

    let videoDuration = 1200; // default fallback 20 mins

    function escapeHtml(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    let sourceTimeOffset = 0;
    video.addEventListener('loadedmetadata', () => {
      if (video.duration && isFinite(video.duration)) {
        videoDuration = video.duration;
      }
      videoErrorOverlay.style.display = 'none';
      refreshData();
    });

    video.addEventListener('error', () => {
      videoErrorOverlay.style.display = 'flex';
    });

    video.addEventListener('timeupdate', () => {
      const cur = video.currentTime + sourceTimeOffset;
      const mins = Math.floor(cur / 60);
      const secs = (cur % 60).toFixed(1);
      timeDisplay.textContent = `${mins.toString().padStart(2, '0')}:${secs.padStart(4, '0')}`;
    });

    function seekTo(timeSec) {
      if (video && isFinite(timeSec)) {
        video.currentTime = Math.min(Math.max(0, timeSec - sourceTimeOffset), Math.max(0, videoDuration - 0.01));
        video.play().catch(() => {});
      }
    }

    async function refreshData() {
      try {
        const [statusRes, evRes, boxRes, heatRes] = await Promise.all([
          fetch('/api/status').then(r => r.json()).catch(() => null),
          fetch('/api/events').then(r => r.json()).catch(() => ({events: []})),
          fetch('/api/boxscore').then(r => r.json()).catch(() => null),
          fetch('/api/heatmap').then(r => r.json()).catch(() => null)
        ]);

        if (statusRes) {
          updateStatus(statusRes);
        }
        const ledgerIds = new Set((evRes.events || []).map(e => e.event_id));
        const displayEvents = (evRes.events || []).concat((evRes.shots || []).filter(e => !ledgerIds.has(e.event_id)));
        displayEvents.sort((a, b) => a.source_time_s - b.source_time_s);
        renderTimeline(displayEvents);
        renderEventList(displayEvents);
        renderBoxscore(boxRes);
        renderCourtShots(evRes.events);
        renderHeatmapDiagnostic(heatRes);
      } catch (err) {
        console.error('Error refreshing dashboard data:', err);
      }
    }

    function updateStatus(status) {
      if (!status) return;
      sourceTimeOffset = status.playback_source_start_s || 0;
      sessionStatus.textContent = `Status: ${escapeHtml(status.status.toUpperCase())}`;
      sessionStatus.textContent += ` | ${status.demo_verdict || 'DEMO_PARTIAL'} | Quality: ${status.quality_gate || 'NOT_ACCEPTED'}`;
      if (status.geometry_status === 'calibrated') {
        geometryBadge.textContent = 'Geometry: Calibrated';
        geometryBadge.className = 'badge badge-confirmed';
      } else {
        geometryBadge.textContent = `Geometry: ${escapeHtml(status.geometry_status || 'Uncalibrated')}`;
        geometryBadge.className = 'badge badge-unresolved';
      }

      if (status.video_exists === false) {
        videoErrorOverlay.style.display = 'flex';
      }
    }

    function renderTimeline(events) {
      timelineBar.innerHTML = '';
      if (!events || events.length === 0) return;

      const dur = videoDuration;
      events.forEach(ev => {
        const t = ev.source_time_s !== undefined ? ev.source_time_s : ev.confirmation_time_s;
        if (t === undefined || t === null) return;
        if (t < sourceTimeOffset || t > sourceTimeOffset + dur) return;
        const posPct = ((t - sourceTimeOffset) / dur) * 100;
        const marker = document.createElement('div');
        const evType = ({shot: 'shot', rebound: 'reb', assist: 'ast', turnover: 'to'})[ev.event_type] || 'shot';
        marker.className = `timeline-marker marker-${evType}`;
        marker.style.left = `${Math.min(Math.max(posPct, 0.5), 98.5)}%`;
        marker.title = `[${t.toFixed(1)}s] ${(ev.event_type || '').toUpperCase()} (${ev.player_id || ev.team_id || 'Unknown'})`;
        marker.onclick = () => seekTo(Math.max(0, t - 1.0));
        timelineBar.appendChild(marker);
      });
    }

    function renderEventList(events) {
      if (!events || events.length === 0) {
        eventList.innerHTML = '<div style="text-align:center; padding:16px; color:var(--text-muted);">No events recorded.</div>';
        eventCount.textContent = '0 events';
        return;
      }

      eventCount.textContent = `${events.length} events`;
      eventList.innerHTML = '';
      events.forEach(ev => {
        const item = document.createElement('div');
        item.className = 'event-item';
        const t = ev.source_time_s !== undefined ? ev.source_time_s : (ev.confirmation_time_s || 0);
        const mins = Math.floor(t / 60);
        const secs = (t % 60).toFixed(1).padStart(4, '0');
        const st = (ev.status || 'unresolved').toLowerCase();
        const badgeClass = st === 'auto_confirmed' ? 'badge-confirmed' : (st === 'provisional' ? 'badge-provisional' : (st === 'void' ? 'badge-void' : 'badge-unresolved'));

        const evTypeStr = escapeHtml(((ev.event_type || 'EVENT') + (ev.outcome ? ' (' + ev.outcome + ')' : '')).toUpperCase());
        const actorStr = escapeHtml(ev.player_id || ev.team_id || 'Unassigned');
        const ptStr = ev.point_value ? `<span style="color:#10b981; font-weight:700; margin-left:6px;">+${ev.point_value} PTS</span>` : '';

        item.innerHTML = `
          <div>
            <span style="font-weight:600; color:var(--accent);">[${mins}:${secs}]</span>
            <span style="margin-left:6px; font-weight:600;">${evTypeStr}</span>
            <span style="color:var(--text-muted); margin-left:6px;">${actorStr}</span>
            ${ptStr}
          </div>
          <div>
            <span class="badge ${badgeClass}">${escapeHtml(st)}</span>
          </div>
        `;
        item.onclick = () => seekTo(Math.max(0, t - 1.0));
        eventList.appendChild(item);
      });
    }

    function renderBoxscore(data) {
      if (!data || !data.team_a || !data.team_b) return;
      const ta = data.team_a;
      const tb = data.team_b;

      scoreHeader.textContent = `${ta.team_name} ${ta.total_score} - ${tb.total_score} ${tb.team_name}`;

      boxscoreBody.innerHTML = '';
      [ta, tb].forEach(team => {
        // Team Total Row
        const trTeam = document.createElement('tr');
        trTeam.className = 'team-header-row';
        const playersList = team.players ? Object.values(team.players) : [];
        const rebDisplay = team.rebounds_total > 0 ? team.rebounds_total : '-';
        const astDisplay = team.assists > 0 ? team.assists : '-';

        trTeam.innerHTML = `
          <td>${escapeHtml(team.team_name.toUpperCase())}</td>
          <td>TOTAL</td>
          <td>${team.total_score}</td>
          <td>${playersList.reduce((s, p) => s + (p.fg_made_1pt || 0), 0)}</td>
          <td>${playersList.reduce((s, p) => s + (p.fg_made_2pt || 0), 0)}</td>
          <td>${playersList.reduce((s, p) => s + (p.ft_made || 0), 0)}</td>
          <td>${rebDisplay}</td>
          <td>${astDisplay}</td>
          <td>${team.turnovers || 0}</td>
          <td>${team.unresolved_shots || 0}</td>
        `;
        boxscoreBody.appendChild(trTeam);

        // Individual Players
        playersList.forEach(p => {
          const trP = document.createElement('tr');
          const pReb = (p.rebounds_total && p.rebounds_total > 0) ? p.rebounds_total : '-';
          const pAst = (p.assists && p.assists > 0) ? p.assists : '-';
          trP.innerHTML = `
            <td>${escapeHtml(p.player_name || p.player_id)}</td>
            <td>#${escapeHtml(p.player_number !== null ? p.player_number : '-')}</td>
            <td><strong>${p.points || 0}</strong></td>
            <td>${p.fg_made_1pt || 0}</td>
            <td>${p.fg_made_2pt || 0}</td>
            <td>${p.ft_made || 0}</td>
            <td>${pReb}</td>
            <td>${pAst}</td>
            <td>${p.turnovers || 0}</td>
            <td>${p.unresolved_shots || 0}</td>
          `;
          boxscoreBody.appendChild(trP);
        });

        // Unassigned Team Row if points occurred
        if (team.team_only_points > 0) {
          const trUn = document.createElement('tr');
          trUn.className = 'team-unassigned-row';
          trUn.innerHTML = `
            <td>Team-Only Unassigned</td>
            <td>-</td>
            <td><strong>${team.team_only_points}</strong></td>
            <td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td>
          `;
          boxscoreBody.appendChild(trUn);
        }
      });
    }

    function renderCourtShots(events) {
      shotMarkersLayer.innerHTML = '';
      if (!events) return;
      const shots = events.filter(e => e.event_type === 'shot');
      let plottedCount = 0;

      shots.forEach(s => {
        const ev = s.evidence || {};
        let cx = null;
        let cy = null;

        // Strict Requirement: NEVER use frame_index % 7 or arbitrary default 5.5m distance.
        // Use verified calibrated 2D court coordinates in meters.
        if (typeof ev.court_x_m === 'number' && typeof ev.court_y_m === 'number') {
          // Half court 15m wide (-7.5m to +7.5m), SVG center at x=250. Scale is ~30.67 px/m.
          // Baseline is y=0m -> SVG cy=20.
          cx = 250 + (ev.court_x_m * 30.67);
          cy = 20 + (ev.court_y_m * 30.67);
        }

        // Plot only when calibrated coordinates are present; otherwise omit to prevent fabricated geometry
        if (cx !== null && cy !== null) {
          plottedCount++;
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', Math.min(Math.max(cx, 25), 475));
          circle.setAttribute('cy', Math.min(Math.max(cy, 25), 375));
          circle.setAttribute('r', '7');
          circle.setAttribute('fill', (s.team_id === 'team_a' || s.team_id === 'team_vie') ? '#ef4444' : '#3b82f6');
          circle.setAttribute('stroke', '#ffffff');
          circle.setAttribute('stroke-width', '1.5');
          circle.setAttribute('cursor', 'pointer');
          circle.onclick = () => seekTo(Math.max(0, (s.source_time_s || 0) - 1.0));

          const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
          const distDesc = ev.court_distance_m ? `${ev.court_distance_m.toFixed(2)}m from rim` : 'calibrated';
          title.textContent = `[${(s.source_time_s || 0).toFixed(1)}s] ${s.point_value ? s.point_value + 'PT Made' : 'Shot'} (${distDesc})`;
          circle.appendChild(title);
          shotMarkersLayer.appendChild(circle);
        }
      });

      if (courtStatusBadge) {
        if (plottedCount > 0) {
          courtStatusBadge.textContent = `${plottedCount} shot(s) plotted from calibrated geometry`;
          courtStatusBadge.style.color = '#10b981';
        } else {
          courtStatusBadge.textContent = 'No calibrated shot positions to plot';
          courtStatusBadge.style.color = '#94a3b8';
        }
      }
    }

    function renderHeatmapDiagnostic(heatRes) {
      if (!heatmapDiagnosticBanner) return;
      if (!heatRes) {
        heatmapDiagnosticBanner.style.display = 'none';
        return;
      }

      if (heatRes.status === 'unavailable') {
        heatmapDiagnosticBanner.style.display = 'block';
        heatmapDiagnosticBanner.innerHTML = `<strong>Heatmap Status: Unavailable</strong> &bull; ${escapeHtml(heatRes.reason || 'Court geometry uncalibrated; fabricated coordinates prohibited.')}`;
      } else if (heatRes.status === 'generated') {
        heatmapDiagnosticBanner.style.display = 'block';
        heatmapDiagnosticBanner.innerHTML = `<strong>Heatmap Status: Active</strong> &bull; ${Number(heatRes.total_player_seconds || 0).toFixed(2)} person-seconds (${heatRes.observations_count || heatRes.observations_tracked || 0} samples).<br><img src="/api/heatmap/image" alt="Observed player court occupancy heatmap" style="max-width:100%;height:auto;margin-top:8px">`;
      } else {
        heatmapDiagnosticBanner.style.display = 'none';
      }
    }

    // Auto-refresh periodically
    setInterval(refreshData, 5000);
    refreshData();
  </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler serving dashboard UI and API endpoints."""

    def __init__(
        self,
        request: Any,
        client_address: Tuple[str, int],
        server: HTTPServer,
        video_path: Optional[Path] = None,
        roster: Optional[RosterConfig] = None,
        ledger: Optional[EventLedger] = None,
        box_engine: Optional[BoxScoreEngine] = None,
        run_state: Optional[Dict[str, Any]] = None,
        heatmap_data: Optional[Dict[str, Any]] = None,
        run_dir: Optional[Path] = None,
        shot_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.video_path = video_path
        self.roster = roster
        self.ledger = ledger
        self.box_engine = box_engine
        self.run_state = run_state or {}
        self.heatmap_data = heatmap_data or {}
        self.run_dir = run_dir
        self.shot_candidates = shot_candidates or []
        super().__init__(request, client_address, server)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout access logs for quiet operation."""
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._serve_html()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/api/events":
            self._serve_events()
        elif path == "/api/boxscore":
            self._serve_boxscore()
        elif path == "/api/heatmap":
            self._serve_heatmap()
        elif path == "/api/heatmap/image":
            image_path = self.run_dir / "heatmap.png" if self.run_dir else None
            if image_path and image_path.is_file():
                data = image_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Heatmap image unavailable")
        elif path == "/api/run_info":
            self._serve_run_info()
        elif path == "/api/export/events":
            self._serve_export_events()
        elif path == "/api/export/boxscore":
            self._serve_export_boxscore()
        elif path == "/api/export/summary":
            self._serve_export_summary()
        elif path == "/api/video":
            self._serve_video()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _serve_html(self) -> None:
        data = DASHBOARD_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_status(self) -> None:
        run_status = self.run_state.get("status", "ready")
        geometry_status = self.run_state.get("geometry", {}).get("status", "uncalibrated")
        status_data = {
            "status": run_status,
            "video_path": str(self.video_path) if self.video_path else None,
            "video_exists": self.video_path.is_file() if self.video_path else False,
            "total_events": len(self.ledger.get_active_events()) if self.ledger else 0,
            "server_utc": datetime.now(timezone.utc).isoformat(),
            "geometry_status": geometry_status,
            "quality_gate": self.run_state.get("quality_gate", "in_progress"),
            "demo_verdict": self.run_state.get("demo_verdict", "DEMO_PARTIAL"),
            "playback_source_start_s": self.run_state.get("playback", {}).get("source_start_s", 0.0),
        }
        self._send_json(status_data)

    def _serve_run_info(self) -> None:
        self._send_json(self.run_state)

    def _serve_heatmap(self) -> None:
        if self.heatmap_data:
            self._send_json(self.heatmap_data)
        else:
            self._send_json({
                "status": "unavailable",
                "reason": "Heatmap data unavailable: court geometry uncalibrated or spatial summary missing.",
                "total_player_seconds": 0.0,
                "observations_tracked": 0,
            })

    def _serve_events(self) -> None:
        events = [e.to_dict() for e in self.ledger.get_active_events()] if self.ledger else []
        self._send_json({"events": events, "count": len(events), "shots": self.shot_candidates})

    def _serve_boxscore(self) -> None:
        if not self.box_engine or not self.ledger:
            self._send_json({"team_a": None, "team_b": None})
            return

        team_a, team_b = self.box_engine.compile(self.ledger)
        self._send_json({
            "team_a": team_a.to_dict(),
            "team_b": team_b.to_dict(),
        })

    def _serve_export_events(self) -> None:
        events = [e.to_dict() for e in self.ledger.get_active_events()] if self.ledger else []
        buf = io.StringIO()
        for e in events:
            buf.write(json.dumps(e, ensure_ascii=False) + "\n")
        data = buf.getvalue().encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-jsonlines; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="events_auto.jsonl"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_export_boxscore(self) -> None:
        if not self.box_engine or not self.ledger:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Box score engine uninitialized")
            return

        team_a, team_b = self.box_engine.compile(self.ledger)
        tmp_csv = io.StringIO()
        BoxScoreEngine.export_csv(team_a, team_b, tmp_csv)
        data = tmp_csv.getvalue().encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="boxscore_auto.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_export_summary(self) -> None:
        payload = json.dumps(self.run_state, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="summary.json"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_video(self) -> None:
        if not self.video_path or not self.video_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Video file not found on local storage")
            return

        file_size = self.video_path.stat().st_size
        range_header = self.headers.get("Range")

        start, end = 0, file_size - 1
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            valid = bool(match and any(match.groups()) and file_size)
            if valid:
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), file_size - 1) if last else file_size - 1
                    valid = start < file_size and end >= start
                else:
                    suffix = int(last)
                    start = max(0, file_size - suffix)
                    valid = suffix > 0
            if not valid:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        try:
            with self.video_path.open("rb") as f:
                f.seek(start)
                remaining = length
                while remaining:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return  # Normal when the browser cancels a request while seeking.

    def _send_json(self, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def load_run_bundle(run_dir: Path) -> Tuple[EventLedger, Dict[str, Any], Dict[str, Any]]:
    """Helper to load all ledger events, run state, and heatmap data from a run output directory."""
    ledger = EventLedger()
    run_state: Dict[str, Any] = {}
    heatmap_data: Dict[str, Any] = {}

    run_dir = Path(run_dir)
    verify_bundle_manifest(run_dir)
    ev_path = run_dir / "events_auto.jsonl"
    if ev_path.is_file():
        for line_number, line in enumerate(ev_path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec_dict = json.loads(line)
                rec = LedgerEventRecord.from_dict(rec_dict)
                ledger.record_event(rec)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"Invalid event at {ev_path.name}:{line_number}: {exc}") from exc

    sum_path = run_dir / "summary.json"
    if (run_dir / "run.json").is_file():
        run_state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    elif sum_path.is_file():
        run_state = json.loads(sum_path.read_text(encoding="utf-8"))

    heat_path = run_dir / "heatmap_summary.json"
    if heat_path.is_file():
        heatmap_data = json.loads(heat_path.read_text(encoding="utf-8"))
    if "stage_counts" in run_state:
        run_state = summarize_run(run_state, heatmap_data)

    return ledger, run_state, heatmap_data


def make_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    video_path: Optional[Path] = None,
    roster: Optional[RosterConfig] = None,
    ledger: Optional[EventLedger] = None,
    box_engine: Optional[BoxScoreEngine] = None,
    run_dir: Optional[Path] = None,
    run_state: Optional[Dict[str, Any]] = None,
    heatmap_data: Optional[Dict[str, Any]] = None,
) -> HTTPServer:
    """Factory creating an HTTPServer configured with dashboard handlers."""
    if run_dir:
        loaded_ledger, loaded_state, loaded_heat = load_run_bundle(Path(run_dir))
        if ledger is None:
            ledger = loaded_ledger
        if run_state is None:
            run_state = loaded_state
        if heatmap_data is None:
            heatmap_data = loaded_heat

    run_state = dict(run_state or {})
    shot_candidates = []
    if run_dir and (Path(run_dir) / "shots_auto.jsonl").is_file():
        for line in (Path(run_dir) / "shots_auto.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                shot = json.loads(line)
                shot_candidates.append({
                    "event_id": shot["shot_id"], "event_type": "shot",
                    "source_time_s": shot.get("outcome_time_s") if shot.get("outcome_time_s") is not None else shot.get("release_time_s"),
                    "status": shot.get("status", "unresolved"),
                    "outcome": shot.get("outcome", "unknown"),
                    "team_id": shot.get("shooter_team_id"),
                    "player_id": shot.get("shooter_player_id"),
                })
    if video_path and Path(video_path).name == "annotated.mp4":
        first_time = run_state.get("source_coverage", {}).get("first_time_s")
        if first_time is not None:
            run_state["playback"] = {"source_start_s": first_time}

    def handler_factory(*args, **kwargs):
        return DashboardRequestHandler(
            *args,
            video_path=video_path,
            roster=roster,
            ledger=ledger,
            box_engine=box_engine,
            run_state=run_state,
            heatmap_data=heatmap_data,
            run_dir=Path(run_dir) if run_dir else None,
            shot_candidates=shot_candidates,
            **kwargs,
        )

    return ThreadingHTTPServer((host, port), handler_factory)
