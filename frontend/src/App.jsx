import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { HomePage } from './components/HomePage';
import { AboutPage } from './components/AboutPage';
import { ImageUploader } from './components/ImageUploader';
import { ProcessingState } from './components/ProcessingState';
import { ResultsView } from './components/ResultsView';
import { HistoryList } from './components/HistoryList';
import { Footer } from './components/Footer';
import { apiService } from './services/api';
import { AlertCircle } from 'lucide-react';

export function App() {
  const getInitialTab = () => {
    if (typeof window === 'undefined') return 'home';
    const hash = window.location.hash.replace('#', '');
    if (['home', 'inspect', 'history', 'about'].includes(hash)) {
      return hash;
    }
    return 'home';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [scanError, setScanError] = useState(null);
  const [scanningFile, setScanningFile] = useState(null);
  const [scanningPreviewUrl, setScanningPreviewUrl] = useState(null);

  useEffect(() => {
    const handleHashChange = () => {
      if (typeof window === 'undefined') return;
      const hash = window.location.hash.replace('#', '');
      if (hash.startsWith('result=')) {
        const fileId = hash.replace('result=', '');
        if (fileId) {
          setIsScanning(true);
          apiService.getScanDetail(fileId)
            .then((data) => {
              setScanResult({
                file_id: data.file_id,
                image_dimensions: { width: 1280, height: 720 },
                ocr_result: {
                  full_text: data.ocr_text,
                  blocks: data.ocr_blocks || [],
                  block_count: data.ocr_blocks?.length || 0,
                  average_confidence: 0.96,
                  execution_time_seconds: 0.42
                },
                structured_data: data.structured_data,
                compliance_report: data.compliance_report
              });
              setActiveTab('inspect');
              setIsScanning(false);
            })
            .catch(() => setIsScanning(false));
        }
      } else if (['home', 'inspect', 'history', 'about'].includes(hash)) {
        setActiveTab(hash);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    // Trigger initial check if result= is in hash
    handleHashChange();

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleStartScan = async (file, isImported, commodityType) => {
    setScanningFile(file);
    const pUrl = URL.createObjectURL(file);
    setScanningPreviewUrl(pUrl);

    setIsScanning(true);
    setScanError(null);
    setScanResult(null);

    try {
      const response = await apiService.inspectPackageFile(file, isImported, commodityType);
      setScanResult(response);
      setIsScanning(false);
    } catch (err) {
      setScanError(err.message || 'Inspection failed. Please ensure the backend is running and the image is clear.');
      setIsScanning(false);
    }
  };

  const handleBackToScan = () => {
    setScanResult(null);
    setScanError(null);
    if (scanningPreviewUrl) {
      URL.revokeObjectURL(scanningPreviewUrl);
      setScanningPreviewUrl(null);
    }
    setScanningFile(null);
  };

  const handleCancelScan = () => {
    setIsScanning(false);
    if (scanningPreviewUrl) {
      URL.revokeObjectURL(scanningPreviewUrl);
      setScanningPreviewUrl(null);
    }
    setScanningFile(null);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAF9] text-slate-900 selection:bg-emerald-100 selection:text-emerald-900">
      
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          if (typeof window !== 'undefined') window.location.hash = tab;
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        
        {activeTab === 'home' && (
          <HomePage
            onStartInspect={() => {
              setActiveTab('inspect');
              if (typeof window !== 'undefined') window.location.hash = 'inspect';
            }}
            onViewHistory={() => {
              setActiveTab('history');
              if (typeof window !== 'undefined') window.location.hash = 'history';
            }}
          />
        )}

        {activeTab === 'inspect' && (
          <div>
            {isScanning ? (
              <ProcessingState
                file={scanningFile}
                previewUrl={scanningPreviewUrl}
                onCancel={handleCancelScan}
              />
            ) : scanResult ? (
              <ResultsView
                result={scanResult}
                onBackToScan={handleBackToScan}
              />
            ) : (
              <div>
                {scanError && (
                  <div className="max-w-4xl mx-auto mt-6 px-4">
                    <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs sm:text-sm flex items-start gap-3 shadow-2xs">
                      <AlertCircle size={20} className="text-rose-600 mt-0.5 shrink-0" />
                      <div>
                        <h4 className="font-bold">Inspection Processing Notice</h4>
                        <p className="text-xs text-rose-700 mt-0.5">{scanError}</p>
                      </div>
                    </div>
                  </div>
                )}

                <ImageUploader
                  onStartScan={handleStartScan}
                  isScanning={isScanning}
                />
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <HistoryList />
        )}

        {activeTab === 'about' && (
          <AboutPage
            onStartInspect={() => {
              setActiveTab('inspect');
              if (typeof window !== 'undefined') window.location.hash = 'inspect';
            }}
          />
        )}

      </main>

      {/* Footer */}
      <Footer onTabChange={(tab) => {
        setActiveTab(tab);
        if (typeof window !== 'undefined') window.location.hash = tab;
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }} />

    </div>
  );
}

export default App;
