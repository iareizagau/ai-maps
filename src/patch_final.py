f = "/app/templates/adventure/follow.html"
c = open(f, encoding="utf-8").read()

# ── PATCH 1: Replace inner dashboard block ─────────────────────────────────
# We use unique anchor strings to slice out the old block and insert the new one

START_ANCHOR = "<!-- Predictive ClimbPro Style Profile -->"
END_ANCHOR = "        </div>\n\n        <!-- EXPANDED VIEW"

new_inner = """        <!-- Predictive Chart embedded as top header strip -->
        <div id="predictive-profile-container" class="relative w-full shrink-0 transition-opacity duration-300" style="height:70px;">
            <div class="absolute top-2 left-4 right-4 flex justify-between items-center z-10 pointer-events-none">
                <span class="text-[9px] font-black text-white/60 uppercase tracking-widest">Proximos 3 km</span>
                <span class="text-[10px] font-black text-emerald-400 uppercase tracking-widest" id="pred-ele-diff">--</span>
            </div>
            <div id="predictive-chart" class="absolute inset-0 w-full h-full opacity-90"></div>
            <div class="absolute bottom-0 left-0 w-full h-[3px] bg-gray-800">
                <div id="compact-progress-bar" class="h-full bg-emerald-500 transition-all duration-500" style="width:0%"></div>
            </div>
            <div class="absolute bottom-[3px] left-0 w-full h-[3px] flex overflow-hidden opacity-70" id="terrain-bar"></div>
        </div>

        <!-- Compact telemetry row -->
        <div id="view-compact" class="flex-1 flex flex-col justify-between px-4 py-3 transition-opacity duration-300">
            <div class="flex justify-between items-end">
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">Tiempo</div>
                    <div class="text-[22px] font-black text-white leading-none font-mono tabular-nums" id="elapsed-time">00:00</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">km/h</div>
                    <div class="text-[22px] font-black text-white leading-none tabular-nums" id="current-speed">0.0</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">km</div>
                    <div class="text-[22px] font-black text-white leading-none tabular-nums" id="dist-traveled">0.00</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">alt m</div>
                    <div class="text-[22px] font-black text-white leading-none tabular-nums" id="current-altitude">--</div>
                </div>
                <button class="w-10 h-10 bg-emerald-500 hover:bg-emerald-400 rounded-full flex items-center justify-center text-white shadow-lg shadow-emerald-500/20 active:scale-95 transition shrink-0 ml-1">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                </button>
            </div>
            <div class="flex items-center justify-end mt-1">
                <div id="intel-alert" class="hidden bg-amber-500 text-amber-950 font-black text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-full animate-pulse mr-auto">
                    Intel: <span id="intel-dist">--</span>m
                </div>
                <button class="text-gray-500 hover:text-white transition active:scale-95 dashboard-toggle p-1 cursor-pointer" aria-label="Expandir vista">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path></svg>
                </button>
            </div>
        </div>

        """

start_idx = c.find(START_ANCHOR)
end_idx = c.find(END_ANCHOR)

if start_idx == -1:
    print("ERROR: start anchor not found")
elif end_idx == -1:
    print("ERROR: end anchor not found")
else:
    print(f"Replacing HTML block: chars {start_idx} to {end_idx}")
    # Keep the 8 spaces before START_ANCHOR (they're already in new_inner)
    c = c[:start_idx] + new_inner + c[end_idx + len(END_ANCHOR) :]
    print("HTML patch applied")

# ── PATCH 2: Fix toggleDashboard JS ────────────────────────────────────────
old_height_line = "            dashboard.style.height = '180px'; // Compact Map view"
new_height_block = """            dashboard.classList.remove('bottom-0', 'left-0', 'right-0', 'rounded-none');
            dashboard.classList.add('bottom-4', 'left-4', 'right-20', 'rounded-3xl', 'border');
            dashboard.style.height = '160px';
            setTimeout(function() { if (typeof predictiveChart !== 'undefined' && predictiveChart) predictiveChart.resize(); }, 520);"""

if old_height_line in c:
    c = c.replace(old_height_line, new_height_block)
    print("JS collapse patch applied")
else:
    print("WARNING: JS collapse line not found")

old_expand_line = "            dashboard.style.height = '100%'; // Fill the container, not 100vh which overflows"
new_expand_block = """            dashboard.classList.remove('bottom-4', 'left-4', 'right-20', 'rounded-3xl', 'border');
            dashboard.classList.add('bottom-0', 'left-0', 'right-0', 'rounded-none');
            dashboard.style.height = '100%';"""

if old_expand_line in c:
    c = c.replace(old_expand_line, new_expand_block)
    print("JS expand patch applied")
else:
    print("WARNING: JS expand line not found")

# ── PATCH 3: Remove dashboard-handle bind ──────────────────────────────────
old_bind = "    document.getElementById('dashboard-handle').addEventListener('click', toggleDashboard);\n    document.querySelectorAll('.dashboard-toggle')"
new_bind = "    document.querySelectorAll('.dashboard-toggle')"
if old_bind in c:
    c = c.replace(old_bind, new_bind)
    print("Handle bind removed")
else:
    print("WARNING: handle bind not found")

open(f, "w", encoding="utf-8").write(c)
print("File saved.")
