import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';
import { CameraView } from './CameraView';
import {
  CameraAccessError,
  type CameraFacing,
  requestCameraStream,
  stopCameraStream,
} from './camera';
import type { PoseFrame } from './pose';
const SERVER_URL =
  import.meta.env.VITE_API_URL ??
  'https://bonfire-partake-city.ngrok-free.dev';
type PrayerName = 'fajr' | 'dhuhr' | 'asr' | 'maghrib' | 'isha';
type HistoryEntry = {
  id: number;
  label: string;
  conf: number;
  time: Date;
};
const PRAYERS: Array<{ value: PrayerName; label: string }> = [
  { value: 'fajr', label: 'الفجر' },
  { value: 'dhuhr', label: 'الظهر' },
  { value: 'asr', label: 'العصر' },
  { value: 'maghrib', label: 'المغرب' },
  { value: 'isha', label: 'العشاء' },
];
const STEP_NAMES: Record<string, string> = {
  qiyam: 'قيام',
  ruku: 'ركوع',
  itidal: 'اعتدال',
  sujud1: 'السجود الأول',
  jalsa: 'الجلوس بين السجدتين',
  sujud2: 'السجود الثاني',
  tashahhud_awsat: 'التشهد الأول',
  tashahhud_akhir: 'التشهد الأخير',
};
function formatTime(d: Date) {
  return d.toLocaleTimeString('ar-EG', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facing, setFacing] = useState<CameraFacing>('user');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [frame, setFrame] = useState<PoseFrame | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [selectedPrayer, setSelectedPrayer] =
    useState<PrayerName | null>(null);
  const [prayerLoading, setPrayerLoading] = useState(false);
  const [prayerError, setPrayerError] = useState('');
  const lastLoggedRef = useRef<string | null>(null);
  useEffect(() => {
    document.title = 'كشف وضعية الصلاة';
    return () => {
      stopCameraStream(stream);
    };
  }, [stream]);
  const handleFrame = useCallback((nextFrame: PoseFrame) => {
    setFrame(nextFrame);
    if (
      nextFrame.detected &&
      nextFrame.predictionEn &&
      nextFrame.predictionEn !== lastLoggedRef.current
    ) {
      lastLoggedRef.current = nextFrame.predictionEn;
      setHistory((prev) =>
        [
          {
            id: Date.now(),
            label:
              nextFrame.predictionAr ??
              nextFrame.predictionEn ??
              '',
            conf: Math.round(nextFrame.classConfidence * 100),
            time: new Date(),
          },
          ...prev,
        ].slice(0, 20),
      );
    }
  }, []);
  const selectPrayer = useCallback(async (prayer: PrayerName) => {
    setPrayerLoading(true);
    setPrayerError('');
    try {
      const response = await fetch(`${SERVER_URL}/select_prayer`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: JSON.stringify({ prayer }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      if (!result.ok) {
        throw new Error(result.message ?? 'تعذر اختيار الصلاة');
      }
      setSelectedPrayer(prayer);
      setFrame(null);
      setHistory([]);
      lastLoggedRef.current = null;
    } catch (err) {
      console.error('PRAYER SELECTION ERROR:', err);
      setPrayerError(
        'تعذر اختيار الصلاة. تأكد أن خادم GPU يعمل ثم حاول مرة أخرى.',
      );
    } finally {
      setPrayerLoading(false);
    }
  }, []);
  const startCamera = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const nextStream = await requestCameraStream(facing);
      setStream((previous) => {
        stopCameraStream(previous);
        return nextStream;
      });
    } catch (err) {
      if (err instanceof CameraAccessError) {
        setError(err.message);
      } else {
        setError('تعذر تشغيل الكاميرا. حاول مرة أخرى.');
      }
    } finally {
      setLoading(false);
    }
  }, [facing]);
  const stopCamera = useCallback(() => {
    setStream((current) => {
      stopCameraStream(current);
      return null;
    });
    setError('');
    setFrame(null);
    lastLoggedRef.current = null;
  }, []);
  const toggleCamera = useCallback(() => {
    if (stream) {
      stopCamera();
    } else {
      void startCamera();
    }
  }, [stream, startCamera, stopCamera]);
  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);
  const sortedProbabilities = frame?.detected
    ? Object.entries(frame.probabilities).sort(
        (a, b) => b[1] - a[1],
      )
    : [];
  const tracking = frame?.tracking ?? null;
  const currentStepName =
    tracking?.expected_pose
      ? STEP_NAMES[tracking.expected_pose] ??
        tracking.expected_pose
      : null;
  const isPrayerActive = Boolean(
    selectedPrayer && tracking?.active,
  );
  const progress =
    tracking?.step_index !== undefined &&
    tracking?.total_steps
      ? Math.min(
          100,
          Math.round(
            (tracking.step_index / tracking.total_steps) * 100,
          ),
        )
      : 0;
  return (
    <div className="stage" dir="rtl">
      <div className="eyebrow">
        <span className="dot" />
        كشف مباشر — خادم GPU بعيد
      </div>
      <h1>
        كشف وضعية <span>الصلاة</span>
      </h1>
      {/* =====================================================
          PRAYER SELECTION
      ====================================================== */}
      <div className="prayer-selector">
        <div className="prayer-selector-title">
          اختر الصلاة
        </div>
        <div className="prayer-grid">
          {PRAYERS.map((prayer) => (
            <button
              key={prayer.value}
              type="button"
              className={`prayer-option${
                selectedPrayer === prayer.value
                  ? ' selected'
                  : ''
              }`}
              onClick={() => void selectPrayer(prayer.value)}
              disabled={prayerLoading}
            >
              {prayer.label}
            </button>
          ))}
        </div>
        {prayerLoading && (
          <div className="prayer-loading">
            <RefreshCcw
              size={15}
              style={{
                animation: 'spin 1s linear infinite',
              }}
            />
            <span>جاري تجهيز الصلاة...</span>
          </div>
        )}
        {prayerError && (
          <div className="prayer-error" role="alert">
            <AlertTriangle size={15} />
            <span>{prayerError}</span>
          </div>
        )}
      </div>
      {/* =====================================================
          CAMERA
      ====================================================== */}
      <div className="frame-wrap">
        <CameraView
          videoRef={videoRef}
          stream={stream}
          facing={facing}
          active={Boolean(stream)}
          loading={loading}
          error={error}
          onRetry={startCamera}
          onFrame={handleFrame}
          frame={frame}
        />
      </div>
      {/* =====================================================
          CAMERA BUTTON
      ====================================================== */}
      <button
        type="button"
        className={`primary-btn${
          stream ? ' stop-mode' : ''
        }`}
        onClick={toggleCamera}
        disabled={loading}
      >
        {loading ? (
          <RefreshCcw
            size={18}
            style={{
              animation: 'spin 1s linear infinite',
            }}
          />
        ) : (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {stream ? (
              <rect
                x="6"
                y="6"
                width="12"
                height="12"
                rx="2"
              />
            ) : (
              <>
                <path d="M4 8a2 2 0 0 1 2-2h1.2a2 2 0 0 0 1.66-.9l.8-1.2a2 2 0 0 1 1.67-.9h1.34a2 2 0 0 1 1.67.9l.8 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8Z" />
                <circle
                  cx="12"
                  cy="13"
                  r="3.4"
                />
              </>
            )}
          </svg>
        )}
        <span>
          {loading
            ? 'جاري التشغيل...'
            : stream
              ? 'إيقاف الكاميرا'
              : 'بدء الكاميرا'}
        </span>
      </button>
      {/* =====================================================
          CAMERA ERROR
      ====================================================== */}
      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={17} />
          <span style={{ flex: 1 }}>{error}</span>
          <button
            type="button"
            className="retry-btn"
            onClick={startCamera}
            disabled={loading}
          >
            إعادة المحاولة
          </button>
        </div>
      )}
      {/* =====================================================
          PRAYER TRACKING
      ====================================================== */}
      {isPrayerActive && tracking && (
        <div className="prayer-tracking">
          <div className="tracking-header">
            <div>
              <div className="tracking-eyebrow">
                الخطوة الحالية
              </div>
              <div className="tracking-step">
                {currentStepName ?? '—'}
              </div>
            </div>
            {tracking.step_index !== undefined &&
              tracking.total_steps !== undefined && (
                <div className="tracking-counter">
                  {Math.min(
                    tracking.step_index + 1,
                    tracking.total_steps,
                  )}{' '}
                  / {tracking.total_steps}
                </div>
              )}
          </div>
          <div className="tracking-progress">
            <div
              className="tracking-progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          {tracking.holding &&
            tracking.duration_in_step !== undefined &&
            tracking.min_required !== undefined && (
              <div className="tracking-holding">
                <span>جاري تثبيت الوضعية...</span>
                <span>
                  {tracking.duration_in_step.toFixed(1)} /{' '}
                  {tracking.min_required.toFixed(1)} ث
                </span>
              </div>
            )}
          {tracking.completed && (
            <div className="tracking-completed">
              تمت الصلاة بنجاح
            </div>
          )}
          {tracking.alert &&
            tracking.alert_type === 'skipped_step' && (
              <div className="tracking-alert skipped">
                <AlertTriangle size={16} />
                <span>
                  {tracking.message ??
                    'يبدو أنك تجاوزت خطوة في الصلاة.'}
                </span>
              </div>
            )}
          {tracking.alert &&
            tracking.alert_type === 'stuck' && (
              <div className="tracking-alert stuck">
                <AlertTriangle size={16} />
                <span>
                  يبدو أنك بقيت في هذه الوضعية مدة أطول
                  من المتوقع.
                </span>
              </div>
            )}
        </div>
      )}
      {/* =====================================================
          DETECTION RESULT
      ====================================================== */}
      <div
        className={`result-sheet${
          stream && frame?.detected ? ' show' : ''
        }`}
      >
        <div className="result-top">
          <span className="result-eyebrow">
            الوضعية المكتشفة
          </span>
          <span className="result-conf-badge">
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
            {frame?.detected
              ? `${Math.round(
                  frame.classConfidence * 100,
                )}%`
              : '—'}
          </span>
        </div>
        <div className="result-name">
          {frame?.predictionAr ?? ''}
        </div>
        <div className="prob-list">
          {sortedProbabilities.map(([label, value]) => (
            <div
              key={label}
              className={`prob-row${
                label === frame?.predictionEn
                  ? ' is-top'
                  : ''
              }`}
            >
              <span className="label">
                {label === 'standing'
                  ? 'قيام'
                  : label === 'bowing'
                    ? 'ركوع'
                    : label === 'sujud'
                      ? 'سجود'
                      : label === 'sitting'
                        ? 'جلوس'
                        : label}
              </span>
              <div className="prob-track">
                <div
                  className="prob-fill"
                  style={{
                    width: `${Math.round(value * 100)}%`,
                  }}
                />
              </div>
              <span className="prob-value">
                {Math.round(value * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>
      {/* =====================================================
          HISTORY
      ====================================================== */}
      <div
        className={`history-section${
          stream ? ' show' : ''
        }`}
      >
        <div className="history-title">
          <span>سجل الكشف</span>
          <button
            type="button"
            className="history-clear"
            onClick={clearHistory}
          >
            مسح السجل
          </button>
        </div>
        <div className="history-list">
          {history.length === 0 ? (
            <div className="history-empty">
              لا يوجد كشف بعد
            </div>
          ) : (
            history.map((entry) => (
              <div
                className="history-item"
                key={entry.id}
              >
                <div className="history-badge">
                  <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle
                      cx="12"
                      cy="8"
                      r="3"
                    />
                    <path d="M6 21v-2a6 6 0 0 1 12 0v2" />
                  </svg>
                </div>
                <div className="history-body">
                  <div className="history-line1">
                    <span className="name">
                      تم كشف: {entry.label}
                    </span>
                    <span className="conf">
                      {entry.conf}%
                    </span>
                  </div>
                  <div className="history-line2">
                    تم حفظ السجل —{' '}
                    {formatTime(entry.time)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
export default App;