import re

with open('src/templates/adventure/follow.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ─── 1. Replace the inner dashboard HTML (lines 70-131) ─────────────────────
# We identify the block from the opening comment to </div> of view-compact

old_inner = '''        
        <!-- Predictive ClimbPro Style Profile -->
        <div id="predictive-profile-container" class="absolute left-4 right-20 z-40 bg-black/60 backdrop-blur-xl border border-white/10 rounded-2xl p-2 transition-opacity duration-300 pointer-events-none opacity-100" style="top: -110px;">
            <div class="flex justify-between items-center mb-1 px-1">
                <span class="text-[9px] font-black text-white/70 uppercase tracking-widest">Próximos 3 km</span>
                <span class="text-[10px] font-black text-emerald-400 uppercase tracking-widest" id="pred-ele-diff">--</span>
            </div>
            <div id="predictive-chart" style="width: 100%; height: 60px;"></div>
        </div>
        
        <!-- Progress Bar (Compact edge) -->
        <div class="absolute top-0 left-0 w-full h-1 bg-gray-800/80 rounded-t-3xl overflow-hidden pointer-events-none">
            <div id="compact-progress-bar" class="h-full bg-[#f85c14] transition-all duration-500" style="width: 0%;"></div>
        </div>

        <!-- Predictive Terrain Bar -->
        <div class="absolute top-1.5 left-0 w-full h-1.5 flex overflow-hidden pointer-events-none px-6 opacity-80" id="terrain-bar">
            <!-- Filled via JS -->
        </div>

        <!-- Drag Handle / Toggle Area -->
        <div id="dashboard-handle" class="w-full flex justify-center py-4 cursor-pointer mt-1">
            <div class="w-12 h-1.5 bg-gray-600 rounded-full"></div>
        </div>

        <div id="view-compact" class="px-8 flex-1 flex flex-col justify-between pb-8 transition-opacity duration-300">
            <!-- Header: Route Name & GPS Status -->
            <div class="flex justify-between items-center mb-6 cursor-pointer group dashboard-toggle" title="Expandir Panel">
                <h3 class="font-bold text-white text-base truncate flex-1 group-hover:text-emerald-400 transition">{{ route.name }}</h3>
                <div id="intel-alert" class="hidden bg-amber-500 text-amber-950 font-black text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full animate-pulse ml-2 mr-3">
                    Intel: <span id="intel-dist">--</span>m
                </div>
                <button class="text-white group-hover:text-gray-300 transition active:scale-95 shrink-0" aria-label="Expandir vista de datos">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path></svg>
                </button>
            </div>

            <!-- Compact Telemetry Row (1x4) -->
            <div class="flex justify-between items-center mb-5 px-1">
                <div class="flex flex-col items-start">
                    <div class="text-[9px] font-black text-gray-500 uppercase tracking-widest mb-0.5">Tiempo</div>
                    <div class="text-xl font-black text-white leading-none font-mono tracking-tighter" id="elapsed-time">00:00</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[9px] font-black text-gray-500 uppercase tracking-widest mb-0.5">Km/h</div>
                    <div class="text-xl font-black text-white leading-none tabular-nums" id="current-speed">0.0</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[9px] font-black text-gray-500 uppercase tracking-widest mb-0.5">Km</div>
                    <div class="text-xl font-black text-white leading-none tabular-nums" id="dist-traveled">0.00</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[9px] font-black text-gray-500 uppercase tracking-widest mb-0.5">Alt (m)</div>
                    <div class="text-xl font-black text-white leading-none tabular-nums" id="current-altitude">--</div>
                </div>
            </div>

            <button class="w-full text-white font-black text-xl uppercase tracking-widest py-4 mt-auto active:scale-95 transition flex items-center justify-center gap-3">
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                Pausar
            </button>
        </div>'''

new_inner = '''        
        <!-- Predictive Chart embedded as top header strip -->
        <div id="predictive-profile-container" class="relative w-full shrink-0 transition-opacity duration-300" style="height:70px;">
            <!-- Label overlay -->
            <div class="absolute top-2 left-4 right-4 flex justify-between items-center z-10 pointer-events-none">
                <span class="text-[9px] font-black text-white/60 uppercase tracking-widest">Próximos 3 km</span>
                <span class="text-[10px] font-black text-emerald-400 uppercase tracking-widest" id="pred-ele-diff">--</span>
            </div>
            <!-- ECharts canvas -->
            <div id="predictive-chart" class="absolute inset-0 w-full h-full opacity-90"></div>
            <!-- Progress bar at bottom edge -->
            <div class="absolute bottom-0 left-0 w-full h-[3px] bg-gray-800">
                <div id="compact-progress-bar" class="h-full bg-emerald-500 transition-all duration-500" style="width:0%"></div>
            </div>
            <!-- Terrain color strip just above progress bar -->
            <div class="absolute bottom-[3px] left-0 w-full h-[3px] flex overflow-hidden opacity-70" id="terrain-bar"></div>
        </div>

        <!-- Compact telemetry row -->
        <div id="view-compact" class="flex-1 flex flex-col justify-between px-4 py-3 transition-opacity duration-300">
            <div class="flex justify-between items-end">
                <!-- Metric: Tiempo -->
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">Tiempo</div>
                    <div class="text-[22px] font-black text-white leading-none font-mono tabular-nums" id="elapsed-time">00:00</div>
                </div>
                <!-- Metric: Velocidad -->
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">km/h</div>
                    <div class="text-[22px] font-black text-white leading-none tabular-nums" id="current-speed">0.0</div>
                </div>
                <!-- Metric: Distancia -->
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">km</div>
                    <div class="text-[22px] font-black text-white leading-none tabular-nums" id="dist-traveled">0.00</div>
                </div>
                <!-- Metric: Altitud -->
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-500 uppercase tracking-widest">alt m</div>
                    <div class="text-[22px] font-black text-white leading-none tabular-nums" id="current-altitude">--</div>
                </div>
                <!-- Pause FAB -->
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
        </div>'''

if old_inner in content:
    content = content.replace(old_inner, new_inner)
    print("✅ HTML inner replaced")
else:
    print("❌ HTML inner NOT found — check whitespace/CRLF")


# ─── 2. Fix toggleDashboard: update height & classes ────────────────────────
old_js = """    function toggleDashboard() {
        dashboardExpanded = !dashboardExpanded;
        if (dashboardExpanded) {
            dashboard.style.height = '100%'; // Fill the container, not 100vh which overflows
            
            // Fade out Top HUD and FABs
            document.getElementById('top-hud').style.opacity = '0';
            document.getElementById('top-hud').style.pointerEvents = 'none';
            document.getElementById('fab-stack').style.opacity = '0';
            document.getElementById('fab-stack').style.pointerEvents = 'none';
            
            // Crossfade views
            viewCompact.style.opacity = '0';
            viewCompact.style.pointerEvents = 'none';
            viewExpanded.style.opacity = '1';
            viewExpanded.style.pointerEvents = 'auto';
            
            // Hide predictive profile
            const predProfile = document.getElementById('predictive-profile-container');
            if (predProfile) {
                predProfile.style.opacity = '0';
                predProfile.style.pointerEvents = 'none';
            }
            
            
        } else {
            dashboard.style.height = '180px'; // Compact Map view
            
            // Fade in Top HUD and FABs
            document.getElementById('top-hud').style.opacity = '1';
            document.getElementById('top-hud').style.pointerEvents = 'auto';
            document.getElementById('fab-stack').style.opacity = '1';
            document.getElementById('fab-stack').style.pointerEvents = 'auto';
            
            // Crossfade views
            viewExpanded.style.opacity = '0';
            viewExpanded.style.pointerEvents = 'none';
            viewCompact.style.opacity = '1';
            viewCompact.style.pointerEvents = 'auto';

            // Show predictive profile
            const predProfile = document.getElementById('predictive-profile-container');
            if (predProfile) {
                predProfile.style.opacity = '1';
            }
        }
    }"""

new_js = """    function toggleDashboard() {
        dashboardExpanded = !dashboardExpanded;
        if (dashboardExpanded) {
            // Go full-screen
            dashboard.classList.remove('bottom-4', 'left-4', 'right-20', 'rounded-3xl', 'border');
            dashboard.classList.add('bottom-0', 'left-0', 'right-0', 'rounded-none');
            dashboard.style.height = '100%';
            
            // Fade out HUD & FABs
            document.getElementById('top-hud').style.opacity = '0';
            document.getElementById('top-hud').style.pointerEvents = 'none';
            document.getElementById('fab-stack').style.opacity = '0';
            document.getElementById('fab-stack').style.pointerEvents = 'none';
            
            // Crossfade
            viewCompact.style.opacity = '0';
            viewCompact.style.pointerEvents = 'none';
            viewExpanded.style.opacity = '1';
            viewExpanded.style.pointerEvents = 'auto';
            
            // Hide chart header
            const predProfile = document.getElementById('predictive-profile-container');
            if (predProfile) predProfile.style.opacity = '0';
            
        } else {
            // Return to floating pill
            dashboard.classList.remove('bottom-0', 'left-0', 'right-0', 'rounded-none');
            dashboard.classList.add('bottom-4', 'left-4', 'right-20', 'rounded-3xl', 'border');
            dashboard.style.height = '160px';
            
            // Restore HUD & FABs
            document.getElementById('top-hud').style.opacity = '1';
            document.getElementById('top-hud').style.pointerEvents = 'auto';
            document.getElementById('fab-stack').style.opacity = '1';
            document.getElementById('fab-stack').style.pointerEvents = 'auto';
            
            // Crossfade
            viewExpanded.style.opacity = '0';
            viewExpanded.style.pointerEvents = 'none';
            viewCompact.style.opacity = '1';
            viewCompact.style.pointerEvents = 'auto';

            // Show chart header
            const predProfile = document.getElementById('predictive-profile-container');
            if (predProfile) predProfile.style.opacity = '1';

            // Resize echarts after transition
            setTimeout(() => { if (predictiveChart) predictiveChart.resize(); }, 520);
        }
    }"""

if old_js in content:
    content = content.replace(old_js, new_js)
    print("✅ JS toggleDashboard replaced")
else:
    print("❌ JS toggleDashboard NOT found — check whitespace/CRLF")


# ─── 3. Fix dashboard-handle binding (no longer needed, bind only .dashboard-toggle) ──
old_bind = """    // Bind toggles
    document.getElementById('dashboard-handle').addEventListener('click', toggleDashboard);
    document.querySelectorAll('.dashboard-toggle').forEach(el => el.addEventListener('click', toggleDashboard));"""

new_bind = """    // Bind toggles — only .dashboard-toggle elements (no drag handle anymore)
    document.querySelectorAll('.dashboard-toggle').forEach(el => el.addEventListener('click', toggleDashboard));"""

if old_bind in content:
    content = content.replace(old_bind, new_bind)
    print("✅ Bind replaced")
else:
    print("❌ Bind NOT found")


with open('src/templates/adventure/follow.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ File written successfully")
