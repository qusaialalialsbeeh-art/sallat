import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Eye,
  Info,
  ScanFace,
  ShieldCheck,
} from 'lucide-react';
import { CameraView } from './CameraView';
import { ControlPanel } from './ControlPanel';
import { StatusPanel } from './StatusPanel';
import {
  CameraAccessError,
  type CameraFacing,
  requestCameraStream,
  stopCameraStream,
} from './camera';
import {
  getBrowserSnapshot,
  usePerformanceStats,
} from './performance';
import './index.css';
function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] =
    useState<MediaStream | null>(null);
  const [facing, setFacing] =
    useState<CameraFacing>('environment');
  const [loading, setLoading] =
    useState(false);
  const [cameraError, setCameraError] =
    useState('');
  const [stats, registerFrame] =
    usePerformanceStats(Boolean(stream));
  const browser = useMemo(
    () => getBrowserSnapshot(),
    [],
  );
  useEffect(() => {
    document.title = 'مراقب الوضعية — مختبر الصلاة';
    return () => {
      stopCameraStream(stream);
    };
  }, [stream]);
  const startCamera = useCallback(async () => {
    setLoading(true);
    setCameraError('');
    try {
      const nextStream =
        await requestCameraStream(facing);
      setStream((previous) => {
        stopCameraStream(previous);
        return nextStream;
      });
    } catch (error) {
      setCameraError(
        error instanceof CameraAccessError
          ? error.message
          : 'تعذّر تشغيل الكاميرا. تحقق من الأذونات وحاول مرة أخرى.',
      );
    } finally {
      setLoading(false);
    }
  }, [facing]);
  const stopCamera = useCallback(() => {
    setStream((current) => {
      stopCameraStream(current);
      return null;
    });
    setCameraError('');
  }, []);
  const switchCamera = useCallback(async () => {
    const nextFacing: CameraFacing =
      facing === 'environment'
        ? 'user'
        : 'environment';
    setLoading(true);
    setCameraError('');
    setStream((current) => {
      stopCameraStream(current);
      return null;
    });
    setFacing(nextFacing);
    try {
      const nextStream =
        await requestCameraStream(nextFacing);
      setStream(nextStream);
    } catch (error) {
      setCameraError(
        error instanceof CameraAccessError
          ? error.message
          : 'تعذّر تبديل الكاميرا. حاول مرة أخرى.',
      );
    } finally {
      setLoading(false);
    }
  }, [facing]);
  return (
    <div className="app-shell" dir="rtl">
      <header className="topbar">
        <div
          className="topbar-inner"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 11,
            }}
          >
            <div className="brand-mark">
              <ScanFace
                size={22}
                strokeWidth={1.8}
              />
            </div>
            <div>
              <div
                className="display"
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                }}
              >
                مختبر الوضعية
              </div>
              <div
                className="eyebrow"
                style={{
                  marginTop: 3,
                  fontSize: 9,
                }}
              >
                STAGE 01 / CAMERA LAB
              </div>
            </div>
          </div>
          <div className="session-pill">
            <span
              className={`status-dot ${
                stream ? 'live' : ''
              }`}
            />
            {stream
              ? 'جلسة محلية نشطة'
              : 'جاهز للبدء'}
          </div>
        </div>
      </header>
      <main className="page">
        <div className="hero-intro fade-up">
          <div>
            <div className="eyebrow">
              معاينة الحركة على الجهاز
            </div>
            <h1 className="display">
              شاهد الوضعية،
              <br />
              بدون مغادرة الصورة.
            </h1>
            <p>
              بث الكاميرا وطبقة التتبع يعملان
              محلياً على هذا الجهاز. لا تسجيل،
              لا رفع، ولا خطوة مخفية.
            </p>
          </div>
          <div className="session-pill">
            <ShieldCheck size={14} />
            خصوصية الجهاز أولاً
          </div>
        </div>
        <div className="lab-grid">
          <div>
            <div
              style={{
                position: 'relative',
                width: '100%',
              }}
            >
              <CameraView
                videoRef={videoRef}
                stream={stream}
                facing={facing}
                active={Boolean(stream)}
                loading={loading}
                error={cameraError}
                onRetry={startCamera}
                onFrame={registerFrame}
              />
            </div>
            <div className="footer-line fade-up delay-3">
              <span>
                <Eye size={14} />
                المعاينة مؤقتة وتنتهي بإيقاف الكاميرا
              </span>
              <span className="mono">
                v0.1 / LOCAL
              </span>
            </div>
          </div>
          <div className="panel-stack">
            <StatusPanel
              active={Boolean(stream)}
              facing={facing}
              browser={browser}
              stats={stats}
              error={cameraError}
            />
            <ControlPanel
              active={Boolean(stream)}
              loading={loading}
              onStart={startCamera}
              onStop={stopCamera}
              onFlip={switchCamera}
            />
            <section className="support-note fade-up delay-3">
              <Info
                size={16}
                style={{
                  flexShrink: 0,
                  marginTop: 2,
                }}
              />
              <span>
                لأفضل نتيجة، ضع الهاتف عمودياً
                على بعد مترين تقريباً، واجعل كامل
                الجسم داخل الإطار.
              </span>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
export default App;