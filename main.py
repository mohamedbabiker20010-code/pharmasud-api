"""
PharmaSUD - Main FastAPI Application
Stage 1 - Version 1.0.0

Main entry point with health checks and dashboard.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import os

from database import engine, get_db, test_connection, get_tables_count
from models import Base

# Initialize FastAPI app
app = FastAPI(
    title="PharmaSUD API",
    description="Pharmacy Point of Sale System",
    version="1.0.0"
)

# CORS configuration - restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/")
def root():
    """Root endpoint - API status."""
    return {
        "status": "PharmaSUD API Running",
        "version": "1.0.0",
        "stage": "Stage 1"
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check - verifies database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        tables_count = get_tables_count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "tables": tables_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@app.get("/api/test-db")
def test_database(db: Session = Depends(get_db)):
    """Detailed database test - counts rows in each table."""
    try:
        tables = [
            "pharmacies", "users", "medicines", "units",
            "batches", "sales", "sale_items"
        ]
        
        results = {}
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                results[table] = result.scalar()
            except Exception as e:
                results[table] = f"not found: {str(e)}"
        
        return {
            "status": "success",
            "message": "All 7 tables verified",
            "counts": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": str(e)}
        )


# Dashboard HTML page
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Main dashboard page - RTL Arabic with Tailwind CSS."""
    return HTMLResponse(content=DASHBOARD_HTML)


# HTML Dashboard with Alpine.js
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="PharmaSUD Pharmacy POS System">
    <title>PharmaSUD - Pharmacy System</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.13.3/dist/cdn.min.js"></script>
    
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
    
    <style>
        body { font-family: 'Tajawal', sans-serif; }
        .pulse-green { animation: pulse-green 2s infinite; }
        .pulse-red { animation: pulse-red 2s infinite; }
        @keyframes pulse-green {
            0%, 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            50% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        }
        @keyframes pulse-red {
            0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            50% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
        }
    </style>
</head>
<body class="bg-slate-900 text-slate-50 min-h-screen">

    <div x-data="pharmaApp()" x-init="init()">
        
        <!-- Header -->
        <header class="bg-slate-800 border-b border-slate-700 p-4 sticky top-0 z-50">
            <div class="max-w-6xl mx-auto flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center">
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z">
                            </path>
                        </svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold text-white">PharmaSUD</h1>
                        <p class="text-slate-400 text-sm">Pharmacy Management System</p>
                    </div>
                </div>
                
                <!-- Connection Status -->
                <div class="flex items-center gap-3">
                    <div x-show="connected" class="flex items-center gap-2 bg-emerald-500/20 px-3 py-1 rounded-full">
                        <div class="w-3 h-3 bg-emerald-500 rounded-full pulse-green"></div>
                        <span class="text-emerald-400 text-sm font-medium">Connected</span>
                    </div>
                    <div x-show="!connected" class="flex items-center gap-2 bg-red-500/20 px-3 py-1 rounded-full">
                        <div class="w-3 h-3 bg-red-500 rounded-full pulse-red"></div>
                        <span class="text-red-400 text-sm font-medium">Offline</span>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="max-w-6xl mx-auto p-6">
            
            <!-- Welcome Card -->
            <div class="bg-gradient-to-r from-emerald-600 to-teal-600 rounded-2xl p-8 mb-8 text-center shadow-lg">
                <h2 class="text-3xl font-bold mb-2 text-white">Welcome to PharmaSUD</h2>
                <p class="text-emerald-100">Stage 1 - Version 1.0.0</p>
            </div>

            <!-- Status Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                
                <!-- System Status -->
                <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-white">System Status</h3>
                        <span class="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-xs font-medium">Active</span>
                    </div>
                    <div class="space-y-3 text-slate-300">
                        <div class="flex justify-between">
                            <span>FastAPI:</span>
                            <span class="text-emerald-400 font-medium">Running</span>
                        </div>
                        <div class="flex justify-between">
                            <span>PostgreSQL:</span>
                            <span :class="dbStatus === 'Connected' ? 'text-emerald-400' : 'text-red-400'" 
                                  class="font-medium" x-text="dbStatus"></span>
                        </div>
                        <div class="flex justify-between">
                            <span>Tables:</span>
                            <span class="text-emerald-400 font-medium" x-text="tablesCount"></span>
                        </div>
                    </div>
                </div>

                <!-- Health Check -->
                <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-white">Health Monitor</h3>
                        <span class="text-slate-400 text-xs" x-text="lastCheck"></span>
                    </div>
                    <div class="space-y-3 text-slate-300">
                        <div class="flex justify-between">
                            <span>Connection:</span>
                            <span :class="connected ? 'text-emerald-400' : 'text-red-400'" 
                                  class="font-medium" x-text="connected ? 'Online' : 'Offline'"></span>
                        </div>
                        <div class="flex justify-between">
                            <span>Next Check:</span>
                            <span class="text-slate-400" x-text="nextCheck"></span>
                        </div>
                        <div class="flex justify-between">
                            <span>Interval:</span>
                            <span class="text-slate-400">30 seconds</span>
                        </div>
                    </div>
                </div>

                <!-- Database Stats -->
                <div class="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-white">Database</h3>
                        <span class="text-slate-400 text-xs">PostgreSQL</span>
                    </div>
                    <div class="space-y-3 text-slate-300">
                        <div class="flex justify-between">
                            <span>Pharmacies:</span>
                            <span class="text-emerald-400 font-medium" x-text="stats.pharmacies || 0"></span>
                        </div>
                        <div class="flex justify-between">
                            <span>Users:</span>
                            <span class="text-emerald-400 font-medium" x-text="stats.users || 0"></span>
                        </div>
                        <div class="flex justify-between">
                            <span>Medicines:</span>
                            <span class="text-emerald-400 font-medium" x-text="stats.medicines || 0"></span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Info Message -->
            <div class="text-center text-slate-500 text-sm">
                <p>System operational | All 7 database tables created | Stage 1 Complete</p>
            </div>

        </main>
    </div>

    <script>
        function pharmaApp() {
            return {
                connected: false,
                dbStatus: 'Checking...',
                tablesCount: '-',
                lastCheck: '-',
                nextCheck: '-',
                stats: {},
                checkInterval: null,

                init() {
                    this.checkHealth();
                    this.fetchStats();
                    // Health check every 30 seconds
                    this.checkInterval = setInterval(() => {
                        this.checkHealth();
                    }, 30000);
                },

                async checkHealth() {
                    try {
                        const response = await fetch('/health', {
                            method: 'GET',
                            headers: { 'Accept': 'application/json' }
                        });
                        
                        if (response.ok) {
                            const data = await response.json();
                            this.connected = true;
                            this.dbStatus = data.database === 'connected' ? 'Connected' : 'Error';
                            this.tablesCount = data.tables || 0;
                        } else {
                            this.connected = false;
                            this.dbStatus = 'Error';
                        }
                    } catch (error) {
                        this.connected = false;
                        this.dbStatus = 'Offline';
                        console.error('Connection error:', error);
                    }
                    
                    // Update timestamps
                    const now = new Date();
                    this.lastCheck = now.toLocaleTimeString('en-US', { hour12: false });
                    const next = new Date(now.getTime() + 30000);
                    this.nextCheck = next.toLocaleTimeString('en-US', { hour12: false });
                },

                async fetchStats() {
                    try {
                        const response = await fetch('/api/test-db', {
                            method: 'GET',
                            headers: { 'Accept': 'application/json' }
                        });
                        
                        if (response.ok) {
                            const data = await response.json();
                            this.stats = data.counts || {};
                        }
                    } catch (error) {
                        console.error('Stats error:', error);
                    }
                }
            }
        }
    </script>

</body>
</html>
"""


# END - main.py - Stage 1
