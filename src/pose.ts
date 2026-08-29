import * as ort from "onnxruntime-web";
// ============================================================
// ONNX RUNTIME WEB
// ============================================================
ort.env.wasm.wasmPaths = "/ort/";
ort.env.wasm.numThreads = 1;
ort.env.wasm.proxy = false;
// ============================================================
// TYPES
// ============================================================
export type PosePoint = {
  x: number;
  y: number;
  confidence: number;
};
export type PoseFrame = {
  points: PosePoint[];
  confidence: number;
  latency: number;
};
// ============================================================
// YOLO26L SETTINGS
// ============================================================
const MODEL_URL = "/models/yolo26l-pose.onnx";
const INPUT_SIZE = 640;
const DETECTIONS = 300;
const VALUES_PER_DETECTION = 57;
const PERSON_CONFIDENCE = 0.25;
const KEYPOINT_CONFIDENCE = 0.25;
// ============================================================
// MODEL STATE
// ============================================================
let session: ort.InferenceSession | null = null;
let loadingPromise:
  Promise<ort.InferenceSession> | null = null;
// ============================================================
// LOAD MODEL
// ============================================================
export async function loadPoseModel(): Promise<ort.InferenceSession> {
  if (session) {
    return session;
  }
  if (loadingPromise) {
    return loadingPromise;
  }
  console.log("================================");
  console.log("LOADING YOLO26L");
  console.log("================================");
  console.log("Model:", MODEL_URL);
  console.log("WASM path: /ort/");
  loadingPromise = (async () => {
    // --------------------------------------------------------
    // Check model URL first
    // --------------------------------------------------------
    const response = await fetch(MODEL_URL, {
      method: "GET",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(
        `تعذّر تحميل نموذج YOLO26L (${response.status})`,
      );
    }
    const contentType =
      response.headers.get("content-type")?.toLowerCase() ?? "";
    if (contentType.includes("text/html")) {
      throw new Error(
        "Vercel يعيد صفحة HTML بدلاً من ملف YOLO26L ONNX.",
      );
    }
    // --------------------------------------------------------
    // Read model into memory
    // --------------------------------------------------------
    const modelBytes =
      await response.arrayBuffer();
    if (modelBytes.byteLength < 1024 * 1024) {
      throw new Error(
        "ملف YOLO26L ONNX غير مكتمل أو حجمه غير صحيح.",
      );
    }
    console.log(
      "MODEL SIZE:",
      modelBytes.byteLength,
      "bytes",
    );
    // --------------------------------------------------------
    // Create ONNX Runtime session
    // --------------------------------------------------------
    return await ort.InferenceSession.create(
      modelBytes,
      {
        executionProviders: ["wasm"],
        graphOptimizationLevel: "all",
      },
    );
  })();
  try {
    session = await loadingPromise;
    console.log("MODEL LOADED");
    console.log(
      "INPUTS:",
      session.inputNames,
    );
    console.log(
      "OUTPUTS:",
      session.outputNames,
    );
    return session;
  } catch (error) {
    loadingPromise = null;
    console.error(
      "YOLO26L MODEL LOADING FAILED:",
      error,
    );
    throw error;
  }
}
// ============================================================
// CREATE INPUT TENSOR
// ============================================================
function createInputTensor(
  video: HTMLVideoElement,
): {
  tensor: ort.Tensor;
  scale: number;
  offsetX: number;
  offsetY: number;
} {
  const videoWidth =
    video.videoWidth;
  const videoHeight =
    video.videoHeight;
  if (
    videoWidth <= 0 ||
    videoHeight <= 0
  ) {
    throw new Error(
      "Video dimensions are not ready.",
    );
  }
  const canvas =
    document.createElement("canvas");
  canvas.width = INPUT_SIZE;
  canvas.height = INPUT_SIZE;
  const context =
    canvas.getContext("2d", {
      willReadFrequently: true,
    });
  if (!context) {
    throw new Error(
      "Could not create canvas context.",
    );
  }
  // ----------------------------------------------------------
  // Letterbox
  // ----------------------------------------------------------
  const scale =
    Math.min(
      INPUT_SIZE / videoWidth,
      INPUT_SIZE / videoHeight,
    );
  const drawWidth =
    videoWidth * scale;
  const drawHeight =
    videoHeight * scale;
  const offsetX =
    (INPUT_SIZE - drawWidth) / 2;
  const offsetY =
    (INPUT_SIZE - drawHeight) / 2;
  context.fillStyle = "black";
  context.fillRect(
    0,
    0,
    INPUT_SIZE,
    INPUT_SIZE,
  );
  context.drawImage(
    video,
    offsetX,
    offsetY,
    drawWidth,
    drawHeight,
  );
  const imageData =
    context.getImageData(
      0,
      0,
      INPUT_SIZE,
      INPUT_SIZE,
    );
  const pixels =
    imageData.data;
  const area =
    INPUT_SIZE * INPUT_SIZE;
  const data =
    new Float32Array(
      area * 3,
    );
  // ----------------------------------------------------------
  // RGBA → RGB / CHW
  // ----------------------------------------------------------
  for (
    let i = 0;
    i < area;
    i++
  ) {
    const pixel =
      i * 4;
    data[i] =
      pixels[pixel] / 255;
    data[area + i] =
      pixels[pixel + 1] / 255;
    data[area * 2 + i] =
      pixels[pixel + 2] / 255;
  }
  return {
    tensor: new ort.Tensor(
      "float32",
      data,
      [
        1,
        3,
        INPUT_SIZE,
        INPUT_SIZE,
      ],
    ),
    scale,
    offsetX,
    offsetY,
  };
}
// ============================================================
// MODEL → VIDEO COORDINATES
// ============================================================
function modelToVideo(
  x: number,
  y: number,
  scale: number,
  offsetX: number,
  offsetY: number,
  videoWidth: number,
  videoHeight: number,
): {
  x: number;
  y: number;
} {
  const originalX =
    (x - offsetX) / scale;
  const originalY =
    (y - offsetY) / scale;
  return {
    x: clamp(
      originalX / videoWidth,
      0,
      1,
    ),
    y: clamp(
      originalY / videoHeight,
      0,
      1,
    ),
  };
}
// ============================================================
// CLAMP
// ============================================================
function clamp(
  value: number,
  min: number,
  max: number,
): number {
  return Math.max(
    min,
    Math.min(max, value),
  );
}
// ============================================================
// DETECT POSE
// ============================================================
export async function detectPose(
  video: HTMLVideoElement,
): Promise<PoseFrame | null> {
  const start =
    performance.now();
  const currentSession =
    await loadPoseModel();
  const input =
    createInputTensor(video);
  const outputs =
    await currentSession.run({
      images: input.tensor,
    });
  const outputName =
    currentSession.outputNames[0];
  const output =
    outputs[outputName];
  if (!output) {
    console.error(
      "YOLO OUTPUT NOT FOUND",
    );
    return null;
  }
  const data =
    output.data as Float32Array;
  // ----------------------------------------------------------
  // Verify output
  // ----------------------------------------------------------
  const expectedLength =
    DETECTIONS *
    VALUES_PER_DETECTION;
  if (
    data.length !==
    expectedLength
  ) {
    console.error(
      "UNEXPECTED YOLO OUTPUT",
    );
    console.error(
      "Expected:",
      expectedLength,
    );
    console.error(
      "Received:",
      data.length,
    );
    return null;
  }
  // ----------------------------------------------------------
  // Find strongest person
  // ----------------------------------------------------------
  let bestDetection = -1;
  let bestConfidence = 0;
  for (
    let i = 0;
    i < DETECTIONS;
    i++
  ) {
    const base =
      i * VALUES_PER_DETECTION;
    const confidence =
      data[base + 4];
    if (
      confidence >=
        PERSON_CONFIDENCE &&
      confidence >
        bestConfidence
    ) {
      bestConfidence =
        confidence;
      bestDetection = i;
    }
  }
  if (
    bestDetection === -1
  ) {
    return null;
  }
  // ----------------------------------------------------------
  // 17 YOLO pose keypoints
  // ----------------------------------------------------------
  const base =
    bestDetection *
    VALUES_PER_DETECTION;
  const points: PosePoint[] =
    [];
  for (
    let i = 0;
    i < 17;
    i++
  ) {
    const keypointIndex =
      base +
      5 +
      i * 3;
    const x =
      data[keypointIndex];
    const y =
      data[keypointIndex + 1];
    const confidence =
      data[keypointIndex + 2];
    const position =
      modelToVideo(
        x,
        y,
        input.scale,
        input.offsetX,
        input.offsetY,
        video.videoWidth,
        video.videoHeight,
      );
    points.push({
      x: position.x,
      y: position.y,
      confidence:
        Number.isFinite(
          confidence,
        )
          ? confidence
          : 0,
    });
  }
  const latency =
    Math.round(
      performance.now() -
        start,
    );
  return {
    points,
    confidence:
      bestConfidence,
    latency,
  };
}
// ============================================================
// SKELETON
// ============================================================
const POSE_LINES:
  Array<[number, number]> =
  [
    [0, 1],
    [0, 2],
    [1, 3],
    [2, 4],
    [5, 6],
    [5, 7],
    [7, 9],
    [6, 8],
    [8, 10],
    [5, 11],
    [6, 12],
    [11, 12],
    [11, 13],
    [13, 15],
    [12, 14],
    [14, 16],
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
  context.clearRect(
    0,
    0,
    width,
    height,
  );
  const point = (
    raw: PosePoint,
  ) => ({
    x:
      (mirrored
        ? 1 - raw.x
        : raw.x) *
      width,
    y:
      raw.y * height,
  });
  context.lineWidth =
    Math.max(
      2,
      width / 350,
    );
  context.lineCap =
    "round";
  context.lineJoin =
    "round";
  for (
    const [a, b] of POSE_LINES
  ) {
    const first =
      frame.points[a];
    const second =
      frame.points[b];
    if (
      !first ||
      !second
    ) {
      continue;
    }
    if (
      first.confidence <
        KEYPOINT_CONFIDENCE ||
      second.confidence <
        KEYPOINT_CONFIDENCE
    ) {
      continue;
    }
    const start =
      point(first);
    const end =
      point(second);
    context.beginPath();
    context.moveTo(
      start.x,
      start.y,
    );
    context.lineTo(
      end.x,
      end.y,
    );
    context.strokeStyle =
      "rgba(233, 151, 107, 0.92)";
    context.stroke();
  }
  for (
    let i = 0;
    i < frame.points.length;
    i++
  ) {
    const raw =
      frame.points[i];
    if (
      raw.confidence <
      KEYPOINT_CONFIDENCE
    ) {
      continue;
    }
    const item =
      point(raw);
    context.beginPath();
    context.arc(
      item.x,
      item.y,
      i === 0 ? 5 : 3.5,
      0,
      Math.PI * 2,
    );
    context.fillStyle =
      i === 0
        ? "#f2c09f"
        : "#e9966b";
    context.fill();
    context.strokeStyle =
      "rgba(18, 43, 43, 0.82)";
    context.lineWidth = 1.5;
    context.stroke();
  }
}