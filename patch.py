import codecs

with codecs.open("src/templates/adventure/follow.html", "r", "utf-8") as f:
    content = f.read()

target = """        <!-- Predictive ClimbPro Style Profile -->
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
        </div>"""

replacement = """        <!-- Predictive Chart as Header Background -->
        <div id="predictive-profile-container" class="relative w-full h-[60px] bg-gradient-to-b from-black/60 to-transparent transition-opacity duration-300 shrink-0">
            <div class="absolute top-2 left-4 right-4 flex justify-between items-center z-10 pointer-events-none">
                <span class="text-[9px] font-black text-white/70 uppercase tracking-widest">{{ route.name }} (Próx 3km)</span>
                <span class="text-[10px] font-black text-emerald-400 uppercase tracking-widest" id="pred-ele-diff">--</span>
            </div>
            <div id="predictive-chart" style="width: 100%; height: 60px;" class="absolute top-0 left-0 w-full h-full opacity-80"></div>
            <!-- Progress Bar embedded at the bottom of the chart header -->
            <div class="absolute bottom-0 left-0 w-full h-1 bg-gray-800/80 overflow-hidden">
                <div id="compact-progress-bar" class="h-full bg-emerald-500 transition-all duration-500" style="width: 0%;"></div>
            </div>
        </div>

        <!-- Predictive Terrain Bar -->
        <div class="w-full h-1 flex overflow-hidden pointer-events-none opacity-80 shrink-0" id="terrain-bar">
            <!-- Filled via JS -->
        </div>

        <div id="view-compact" class="flex-1 flex flex-col px-5 py-3 transition-opacity duration-300 relative z-20">
            <!-- Compact Telemetry Row -->
            <div class="flex justify-between items-end mb-2 mt-1">
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-400 uppercase tracking-widest mb-0.5">Tiempo</div>
                    <div class="text-2xl font-black text-white leading-none font-mono tracking-tighter" id="elapsed-time">00:00</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-400 uppercase tracking-widest mb-0.5">Km/h</div>
                    <div class="text-2xl font-black text-white leading-none tabular-nums tracking-tighter" id="current-speed">0.0</div>
                </div>
                <div class="flex flex-col items-start">
                    <div class="text-[8px] font-black text-gray-400 uppercase tracking-widest mb-0.5">Km</div>
                    <div class="text-2xl font-black text-white leading-none tabular-nums tracking-tighter" id="dist-traveled">0.00</div>
                </div>
                
                <!-- Circular Pause Button (FAB style) -->
                <button class="w-10 h-10 bg-emerald-500 hover:bg-emerald-400 rounded-full flex items-center justify-center text-white shadow-lg shadow-emerald-500/20 active:scale-95 transition-transform shrink-0">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                </button>
            </div>
            
            <div class="flex items-center justify-between mt-auto">
                <div id="intel-alert" class="hidden bg-amber-500 text-amber-950 font-black text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-full animate-pulse">
                    Intel: <span id="intel-dist">--</span>m
                </div>
                <!-- Expand trigger -->
                <button class="ml-auto text-gray-400 hover:text-white transition active:scale-95 dashboard-toggle cursor-pointer p-1" aria-label="Expandir vista">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path></svg>
                </button>
            </div>
        </div>"""

if target.replace("\\r\\n", "\\n") in content.replace("\\r\\n", "\\n"):
    print("Found HTML! Replacing...")
    content = content.replace("\\r\\n", "\\n").replace(
        target.replace("\\r\\n", "\\n"), replacement
    )
else:
    print("NOT FOUND HTML")

target_js = """    function toggleDashboard() {
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

replacement_js = """    function toggleDashboard() {
        dashboardExpanded = !dashboardExpanded;
        if (dashboardExpanded) {
            dashboard.style.height = '100%'; // Fill the container
            
            // Expand visually
            dashboard.classList.remove('bottom-4', 'left-4', 'right-20', 'rounded-3xl');
            dashboard.classList.add('bottom-0', 'left-0', 'w-full', 'rounded-none');
            
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
            
        } else {
            dashboard.style.height = '160px'; // Compact Map view
            
            // Collapse visually
            dashboard.classList.remove('bottom-0', 'left-0', 'w-full', 'rounded-none');
            dashboard.classList.add('bottom-4', 'left-4', 'right-20', 'rounded-3xl');
            
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
        }
    }"""

if target_js.replace("\\r\\n", "\\n") in content.replace("\\r\\n", "\\n"):
    print("Found JS! Replacing...")
    content = content.replace("\\r\\n", "\\n").replace(
        target_js.replace("\\r\\n", "\\n"), replacement_js
    )
else:
    print("NOT FOUND JS")

with codecs.open("src/templates/adventure/follow.html", "w", "utf-8") as f:
    f.write(content)
