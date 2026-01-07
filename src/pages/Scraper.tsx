import { useState } from 'react';
import { Play, Square, Calendar, Clock, Download, AlertCircle } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { Terminal } from '@/components/dashboard/Terminal';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export default function Scraper() {
  const [isRunning, setIsRunning] = useState(false);
  const [targetDate, setTargetDate] = useState(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.toISOString().split('T')[0];
  });
  
  const [stats, setStats] = useState({
    total: 0,
    downloaded: 0,
    failed: 0,
    elapsed: 0,
  });

  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: '1',
      timestamp: '10:30:00',
      level: 'info',
      message: 'Scraper ready. Click "Run Scraper" to start.',
    },
  ]);

  const addLog = (level: LogEntry['level'], message: string) => {
    const now = new Date().toLocaleTimeString('en-GB');
    setLogs(prev => [...prev, {
      id: Date.now().toString(),
      timestamp: now,
      level,
      message,
    }]);
  };

  const handleRunScraper = async () => {
    if (isRunning) return;

    setIsRunning(true);
    setLogs([]);
    setStats({ total: 0, downloaded: 0, failed: 0, elapsed: 0 });

    addLog('info', `Starting scraper for date: ${targetDate}`);
    addLog('info', 'Category filter: Fournitures (2)');
    addLog('info', 'Connecting to marchespublics.gov.ma...');

    // Simulate scraper phases
    await simulatePhase('Launching browser...', 1000);
    addLog('success', 'Browser ready');
    
    await simulatePhase('Navigating to search page...', 1500);
    addLog('success', 'Search page loaded');
    
    await simulatePhase('Applying filters...', 800);
    addLog('info', `Date range: ${formatDate(targetDate)} to ${formatDate(targetDate)}`);
    
    await simulatePhase('Collecting tender links...', 2000);
    const mockTotal = Math.floor(Math.random() * 20) + 5;
    setStats(prev => ({ ...prev, total: mockTotal }));
    addLog('success', `Found ${mockTotal} tender links`);

    // Simulate downloads
    for (let i = 1; i <= mockTotal; i++) {
      await simulatePhase(`Downloading tender ${i}/${mockTotal}...`, 300);
      const success = Math.random() > 0.1;
      if (success) {
        setStats(prev => ({ ...prev, downloaded: prev.downloaded + 1 }));
        addLog('success', `Downloaded: tender_${i}_dce.zip`);
      } else {
        setStats(prev => ({ ...prev, failed: prev.failed + 1 }));
        addLog('error', `Failed: tender_${i} (timeout)`);
      }
    }

    addLog('info', '═'.repeat(40));
    addLog('success', 'Scraper completed');
    setIsRunning(false);
  };

  const handleStopScraper = () => {
    addLog('warning', 'Stopping scraper...');
    setIsRunning(false);
  };

  const simulatePhase = (message: string, delay: number) => {
    return new Promise<void>(resolve => {
      addLog('info', message);
      setTimeout(() => {
        setStats(prev => ({ ...prev, elapsed: prev.elapsed + delay / 1000 }));
        resolve();
      }, delay);
    });
  };

  const formatDate = (dateStr: string) => {
    const [year, month, day] = dateStr.split('-');
    return `${day}/${month}/${year}`;
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold">Scraper Control</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Download tenders from marchespublics.gov.ma
          </p>
        </div>

        {/* Alert */}
        <div className="flex items-start gap-3 p-4 rounded-lg bg-warning/10 border border-warning/20">
          <AlertCircle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-warning">Backend Required</p>
            <p className="text-muted-foreground mt-1">
              The scraper runs on your local Python backend (FastAPI). Make sure 
              <code className="mx-1 px-1.5 py-0.5 bg-muted rounded font-mono text-xs">python main.py</code> 
              is running on port 8000.
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* Configuration */}
          <div className="data-card space-y-4">
            <h2 className="font-medium">Configuration</h2>
            
            <div className="space-y-2">
              <Label htmlFor="targetDate">Target Date (Mise en ligne)</Label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="targetDate"
                  type="date"
                  value={targetDate}
                  onChange={(e) => setTargetDate(e.target.value)}
                  className="pl-10"
                  disabled={isRunning}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Downloads tenders published on this date
              </p>
            </div>

            <div className="pt-2 flex gap-3">
              {!isRunning ? (
                <Button onClick={handleRunScraper} className="flex-1">
                  <Play className="w-4 h-4 mr-2" />
                  Run Scraper
                </Button>
              ) : (
                <Button onClick={handleStopScraper} variant="destructive" className="flex-1">
                  <Square className="w-4 h-4 mr-2" />
                  Stop Scraper
                </Button>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <StatCard 
                label="Total Found" 
                value={stats.total} 
                icon={<Download className="w-4 h-4" />}
              />
              <StatCard 
                label="Downloaded" 
                value={stats.downloaded} 
                variant="success"
              />
              <StatCard 
                label="Failed" 
                value={stats.failed} 
                variant="destructive"
              />
              <StatCard 
                label="Elapsed" 
                value={`${stats.elapsed.toFixed(1)}s`}
                icon={<Clock className="w-4 h-4" />}
              />
            </div>
          </div>
        </div>

        {/* Terminal */}
        <Terminal 
          title="Scraper Output" 
          logs={logs} 
          maxHeight="400px" 
        />
      </div>
    </AppLayout>
  );
}
