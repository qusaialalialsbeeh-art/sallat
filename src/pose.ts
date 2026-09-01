// ============================================================
// REMOTE POSE SERVER (Kaggle GPU + ngrok)
// ============================================================
const SERVER_URL = import.meta.env.VITE_API_URL ?? "https://bonfire-partake-city.ngrok-free.dev";
const KEYPOINT_CONFIDENCE = 0.4;

// ============================================================
// TYPES
// ============================================================
export type PosePoint = {
  x: number; // normalized 0-1
  y: number; // normalized 0-1
  confidence: number;
};

export type PoseFrame = {
  detected: boolean;
  points: PosePoint[];
  personConfidence: number;
  latency: number;
  predictionEn: string | null;
  predictionAr: string | null;
  classConfidence: number;
  probabilities: Record<string, number>;
};

export async function loadPoseModel(): Promise<null> {
  return null; // ما في تحميل محلي، السيرفر جاهز
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v));
}

// ============================================================
// DETECT POSE (يرسل الفريم للسيرفر البعيد)
// ============================================================
export async function detectPose(video: HTMLVideoElement): Promise<PoseFrame | null> {
  const start = performance.now();

  const videoWidth = video.videoWidth;
  const videoHeight = video.videoHeight;
  if (videoWidth <= 0 || videoHeight <= 0) return null;

  const canvas = document.createElement("canvas");
  canvas.width = videoWidth;
  canvas.height = videoHeight;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.drawImage(video, 0, 0, videoWidth, videoHeight);

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, "image/jpeg", 0.85);
  });
  if (!blob) return null;

  const formData = new FormData();
  formData.append("file", blob, "frame.jpg");

  let response: Response;
  try {
    response = await fetch(`${SERVER_URL}/classify`, {
      method: "POST",
      headers: { "ngrok-skip-browser-warning": "true" },
      body: formData,
    });
  } catch (error) {
    console.error("REMOTE SERVER UNREACHABLE:", error);
    return null;
  }

  if (!response.ok) {
    console.error("REMOTE SERVER ERROR:", response.status);
    return null;
  }

  const result = await response.json();
  const latency = Math.round(performance.now() - start);

  if (!result.detected) {
    return {
      detected: false,
      points: [],
      personConfidence: 0,
      latency,
      predictionEn: null,
      predictionAr: null,
      classConfidence: 0,
      probabilities: {},
    };
  }

  const rawPoints: [number, number][] = result.points;
  const rawConfs: number[] = result.point_confidences;

  const points: PosePoint[] = rawPoints.map(([x, y], i) => ({
    x: clamp(x / videoWidth, 0, 1),
    y: clamp(y / videoHeight, 0, 1),
    confidence: rawConfs[i] ?? 0,
  }));

  return {
    detected: true,
    points,
    personConfidence: result.person_confidence,
    latency,
    predictionEn: result.prediction_en,
    predictionAr: result.prediction_ar,
    classConfidence: result.confidence,
    probabilities: result.probabilities,
  };
}

// ============================================================
// SKELETON LINES
// ============================================================
const POSE_LINES: Array<[number, number]> = [
  [0, 1], [0, 2], [1, 3], [2, 4],
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
];

// ============================================================
// DRAW POSE
// ============================================================
export function drawPoseOverlay(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  frame: PoseFrame,
  mirrored: boolean,
) {
  context.clearRect(0, 0, width, height);
  if (!frame.detected) return;

  const point = (raw: PosePoint) => {
    const normalizedX = mirrored ? 1 - raw.x : raw.x;
    return { x: normalizedX * width, y: raw.y * height };
  };

  context.lineWidth = Math.max(3, width / 300);
  context.lineCap = "round";
  context.lineJoin = "round";

  for (const [a, b] of POSE_LINES) {
    const first = frame.points[a];
    const second = frame.points[b];
    if (!first || !second) continue;
    if (first.confidence < KEYPOINT_CONFIDENCE || second.confidence < KEYPOINT_CONFIDENCE) continue;
    const start = point(first);
    const end = point(second);
    context.beginPath();
    context.moveTo(start.x, start.y);
    context.lineTo(end.x, end.y);
    context.strokeStyle = "rgba(233, 151, 107, 0.95)";
    context.stroke();
  }

  frame.points.forEach((raw, i) => {
    if (raw.confidence < KEYPOINT_CONFIDENCE) return;
    const item = point(raw);
    context.beginPath();
    context.arc(item.x, item.y, i === 0 ? 7 : 5, 0, Math.PI * 2);
    context.fillStyle = i === 0 ? "#f2c09f" : "#e9966b";
    context.fill();
    context.strokeStyle = "rgba(18, 43, 43, 0.9)";
    context.lineWidth = 2;
    context.stroke();
  });
}