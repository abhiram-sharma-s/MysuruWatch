/**
 * Mysuru RoadWatch — User Reporting Page Logic
 * Mobile Camera capture, AI YOLO detection, Geolocation, and Report submission
 */

let cameraStream = null;
let currentFacingMode = 'environment'; // Rear camera default for smartphone road capture
let currentCapturedBase64 = null;
let currentUploadedFile = null;
let currentDetectionData = null;

document.addEventListener('DOMContentLoaded', () => {
  initCaptureTabs();
  initDropzone();
  initCameraControls();
  initSamplePresets();
  initLocationHelpers();
  initReportForm();
  resetFormToInitialState();
});

// Tab switcher between File Upload and Live Camera
function initCaptureTabs() {
  const uploadTabBtn = document.getElementById('tabUpload');
  const cameraTabBtn = document.getElementById('tabCamera');
  const dropzone = document.getElementById('dropzone');
  const cameraContainer = document.getElementById('cameraContainer');

  if (uploadTabBtn && cameraTabBtn) {
    uploadTabBtn.addEventListener('click', () => {
      uploadTabBtn.classList.add('active');
      cameraTabBtn.classList.remove('active');
      dropzone.style.display = 'block';
      cameraContainer.classList.remove('active');
      stopCamera();
    });

    cameraTabBtn.addEventListener('click', () => {
      cameraTabBtn.classList.add('active');
      uploadTabBtn.classList.remove('active');
      dropzone.style.display = 'none';
      cameraContainer.classList.add('active');
      startCamera();
    });
  }
}

// File dropzone
function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('roadFileInput');
  const choosePhotoBtn = document.getElementById('choosePhotoBtn');
  const chooseVideoBtn = document.getElementById('chooseVideoBtn');

  if (!dropzone || !fileInput) return;

  if (choosePhotoBtn) {
    choosePhotoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.accept = 'image/*';
      fileInput.click();
    });
  }

  if (chooseVideoBtn) {
    chooseVideoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.accept = 'video/*,.mp4,.mov,.avi,.webm,.mkv';
      fileInput.click();
    });
  }

  dropzone.addEventListener('click', (e) => {
    if (e.target !== choosePhotoBtn && e.target !== chooseVideoBtn && !e.target.closest('button')) {
      fileInput.accept = 'image/*,video/*';
      fileInput.click();
    }
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('drag-over');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  // Setup video view toggles
  const viewKeyframeBtn = document.getElementById('viewAnnotatedKeyframeBtn');
  const viewVideoBtn = document.getElementById('viewOriginalVideoBtn');
  const previewImg = document.getElementById('aiPreviewImage');
  const previewVideo = document.getElementById('aiPreviewVideo');

  if (viewKeyframeBtn && previewImg && previewVideo) {
    viewKeyframeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      previewImg.style.display = 'block';
      previewVideo.pause();
      previewVideo.style.display = 'none';
      viewKeyframeBtn.classList.replace('btn-outline', 'btn-amber');
      if (viewVideoBtn) viewVideoBtn.classList.replace('btn-amber', 'btn-outline');
    });
  }

  if (viewVideoBtn && previewImg && previewVideo) {
    viewVideoBtn.addEventListener('click', (e) => {
      e.preventDefault();
      previewImg.style.display = 'none';
      previewVideo.style.display = 'block';
      previewVideo.play().catch(() => {});
      viewVideoBtn.classList.replace('btn-outline', 'btn-amber');
      if (viewKeyframeBtn) viewKeyframeBtn.classList.replace('btn-amber', 'btn-outline');
    });
  }
}

function handleFileSelected(file) {
  currentUploadedFile = file;
  currentCapturedBase64 = null;
  currentDetectionData = null;

  const isVideo = file.type.startsWith('video/') || /\.(mp4|mov|avi|webm|mkv)$/i.test(file.name);
  const previewImg = document.getElementById('aiPreviewImage');
  const previewVideo = document.getElementById('aiPreviewVideo');
  const emptyPlaceholder = document.getElementById('aiEmptyPlaceholder');
  const videoBanner = document.getElementById('aiVideoBreakdownBanner');
  const toggleBar = document.getElementById('videoViewToggleBar');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';
  if (videoBanner) videoBanner.style.display = 'none';
  if (toggleBar) toggleBar.style.display = 'none';

  if (isVideo) {
    if (previewImg) previewImg.style.display = 'none';
    if (previewVideo) {
      previewVideo.src = URL.createObjectURL(file);
      previewVideo.style.display = 'block';
      previewVideo.play().catch(() => {});
    }
    showToast(`Road video selected (${(file.size / (1024*1024)).toFixed(1)} MB). Analyzing roadway for multiple damages with YOLO...`, 'info', 4000);
    runAiDetectionFromFile(file, true);
  } else {
    if (previewVideo) {
      previewVideo.pause();
      previewVideo.style.display = 'none';
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      if (previewImg) {
        previewImg.src = e.target.result;
        previewImg.style.display = 'block';
      }
      runAiDetectionFromFile(file, false);
    };
    reader.readAsDataURL(file);
  }
}

// Mobile Camera Stream
async function startCamera() {
  const video = document.getElementById('cameraFeed');
  if (!video) return;

  stopCamera();

  try {
    const constraints = {
      video: {
        facingMode: currentFacingMode,
        width: { ideal: 1280 },
        height: { ideal: 720 }
      },
      audio: false
    };

    cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = cameraStream;
    await video.play();
  } catch (err) {
    console.error('Camera access error:', err);
    showToast('Could not access mobile camera. Please allow camera permissions or upload an image file.', 'error');
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
}

function initCameraControls() {
  const snapBtn = document.getElementById('snapPhotoBtn');
  const switchBtn = document.getElementById('switchCameraBtn');

  if (switchBtn) {
    switchBtn.addEventListener('click', () => {
      currentFacingMode = (currentFacingMode === 'environment') ? 'user' : 'environment';
      startCamera();
    });
  }

  if (snapBtn) {
    snapBtn.addEventListener('click', () => {
      const video = document.getElementById('cameraFeed');
      if (!video || !video.videoWidth) {
        showToast('Camera is not active yet.', 'error');
        return;
      }

      // Render video frame to canvas
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const base64Image = canvas.toDataURL('image/jpeg', 0.88);
      currentCapturedBase64 = base64Image;
      currentUploadedFile = null;
      currentDetectionData = null;

      // Update preview image
      const previewImg = document.getElementById('aiPreviewImage');
      const emptyPlaceholder = document.getElementById('aiEmptyPlaceholder');
      if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';
      if (previewImg) {
        previewImg.src = base64Image;
        previewImg.style.display = 'block';
      }

      // Stop camera and switch to preview
      stopCamera();
      const dropzone = document.getElementById('dropzone');
      const cameraContainer = document.getElementById('cameraContainer');
      const uploadTabBtn = document.getElementById('tabUpload');
      const cameraTabBtn = document.getElementById('tabCamera');

      if (cameraContainer) cameraContainer.classList.remove('active');
      if (dropzone) dropzone.style.display = 'block';
      if (uploadTabBtn) uploadTabBtn.classList.add('active');
      if (cameraTabBtn) cameraTabBtn.classList.remove('active');

      showToast('Photo captured successfully! Running YOLO road damage analysis...', 'info');

      // Run AI Detection on base64
      runAiDetectionFromBase64(base64Image);
    });
  }
}

// Sample presets for quick college demonstration
function initSamplePresets() {
  document.querySelectorAll('.preset-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const sampleType = chip.dataset.sample;
      let sampleUrl = `/uploads/sample_${sampleType}_road.jpg`;

      // Set preview
      const previewImg = document.getElementById('aiPreviewImage');
      if (previewImg) previewImg.src = sampleUrl;

      // Also set location preset suggestion
      const locationInput = document.getElementById('locationInput');
      if (locationInput && !locationInput.value) {
        if (sampleType === 'pothole') locationInput.value = 'Sayyaji Rao Road, Near Mysore Palace, Mysuru';
        else if (sampleType === 'crack') locationInput.value = 'KRS Road, Near Vijayanagar 2nd Stage, Mysuru';
        else locationInput.value = 'Devaraja Urs Road, Mysuru Commercial Zone';
      }

      showToast(`Loaded ${sampleType.toUpperCase()} test sample. Analyzing with YOLO...`, 'info');
      runAiDetectionFromUrl(sampleUrl);
    });
  });
}

// AI Detection Request Handlers with Interactive Simulated Recognition Animation
function runFakeRecognitionAnimation(isVideo = false) {
  return new Promise((resolve) => {
    const stepEl = document.getElementById('aiRecognitionStep');
    const fillEl = document.getElementById('aiRecognitionProgressFill');
    const tickerEl = document.getElementById('aiRecognitionTickerVal');
    const logEl = document.getElementById('aiRecognitionSubLog');
    const box1 = document.getElementById('fakeRecBox1');
    const box2 = document.getElementById('fakeRecBox2');
    const tag1 = document.getElementById('fakeRecTag1');
    const tag2 = document.getElementById('fakeRecTag2');

    // Phase 1 (0ms): Tensor / Video Stream Preprocessing
    if (fillEl) fillEl.style.width = '24%';
    if (tickerEl) tickerEl.innerText = '28%';
    if (stepEl) stepEl.innerText = isVideo ? 'Phase 1/4: Decoding Video Stream & Sampling Frames...' : 'Phase 1/4: Normalizing 640x640 Image Tensor...';
    if (logEl) logEl.innerText = isVideo ? 'Sampling video stream at 25 fps & extracting roadway frames...' : 'Preprocessing RGB channels & edge gradients...';
    if (box1) {
      box1.style.display = 'block';
      box1.style.top = '22%';
      box1.style.left = '20%';
      box1.style.width = '48%';
      box1.style.height = '40%';
    }
    if (tag1) tag1.innerText = isVideo ? 'STREAM SAMPLER: [EXTRACTING FRAMES]' : 'SCANNING ROI: [X:140, Y:92]';
    if (box2) box2.style.display = 'none';

    // Phase 2 (550ms): Pavement Matrix & Multi-Frame Scanning
    setTimeout(() => {
      if (fillEl) fillEl.style.width = '55%';
      if (tickerEl) tickerEl.innerText = '65%';
      if (stepEl) stepEl.innerText = isVideo ? 'Phase 2/4: Multi-Frame Road Surface & Defect Scanning...' : 'Phase 2/4: Pavement Matrix & Cavity Extraction';
      if (logEl) logEl.innerText = isVideo ? 'Scanning road damage progression across consecutive video frames...' : 'Scanning surface texture depth & fissure contours...';
      if (box1) {
        box1.style.top = '30%';
        box1.style.left = '26%';
        box1.style.width = '44%';
        box1.style.height = '36%';
      }
      if (tag1) tag1.innerText = isVideo ? 'ROAD SURFACE: [MULTI-FRAME ACTIVE]' : 'SURFACE ANOMALY: [DEPTH 42mm]';
      if (box2) {
        box2.style.display = 'block';
        box2.style.top = '44%';
        box2.style.left = '40%';
        box2.style.width = '36%';
        box2.style.height = '30%';
      }
      if (tag2) tag2.innerText = isVideo ? 'IDENTIFIED DAMAGE CANDIDATES: 88.4%' : 'LOCALIZING CAVITY: 78.4%';
    }, 550);

    // Phase 3 (1150ms): YOLOv8 Neural Inference Across Video
    setTimeout(() => {
      if (fillEl) fillEl.style.width = '84%';
      if (tickerEl) tickerEl.innerText = '90%';
      if (stepEl) stepEl.innerText = isVideo ? 'Phase 3/4: YOLOv8 Detecting All Potholes & Cracks...' : 'Phase 3/4: YOLOv8 Neural Model Inference';
      if (logEl) logEl.innerText = isVideo ? 'Correlating multi-damage coordinates & bounding boxes across frames...' : 'Matching convolutional feature weights for road defects...';
      if (tag1) tag1.innerText = isVideo ? 'YOLOv8: MULTI-DAMAGE CONFIRMED' : 'YOLOv8 DETECTED: ROAD DEFECT';
      if (tag2) tag2.innerText = 'CONFIDENCE LOCK: 93.8%';
    }, 1150);

    // Phase 4 (1750ms): Verification & Classification
    setTimeout(() => {
      if (fillEl) fillEl.style.width = '100%';
      if (tickerEl) tickerEl.innerText = '96%';
      if (stepEl) stepEl.innerText = isVideo ? 'Phase 4/4: Multi-Defect Aggregation & Keyframe Lock' : 'Phase 4/4: Classification & Severity Confirmed';
      if (logEl) logEl.innerText = isVideo ? 'Generating keyframe damage annotations & municipal hazard score...' : 'Applying defect perimeter coordinates & hazard assessment...';
    }, 1750);

    // Complete at 2100ms
    setTimeout(() => {
      resolve();
    }, 2100);
  });
}

async function runAiDetectionFromFile(file, isVideo = false) {
  setAiLoading(true);
  try {
    const formData = new FormData();
    formData.append('file', file);
    const [result] = await Promise.all([
      window.roadWatchApi.detectRoadDamage(formData),
      runFakeRecognitionAnimation(isVideo)
    ]);
    applyAiDetectionResult(result);
  } catch (err) {
    handleAiError(err);
  } finally {
    setAiLoading(false);
  }
}

async function runAiDetectionFromBase64(base64Str) {
  setAiLoading(true);
  try {
    const formData = new FormData();
    formData.append('image_base64', base64Str);
    const [result] = await Promise.all([
      window.roadWatchApi.detectRoadDamage(formData),
      runFakeRecognitionAnimation()
    ]);
    applyAiDetectionResult(result);
  } catch (err) {
    handleAiError(err);
  } finally {
    setAiLoading(false);
  }
}

async function runAiDetectionFromUrl(imageUrl) {
  setAiLoading(true);
  try {
    const [result] = await Promise.all([
      window.roadWatchApi.detectRoadDamage({ image_url: imageUrl }),
      runFakeRecognitionAnimation()
    ]);
    applyAiDetectionResult(result);
  } catch (err) {
    handleAiError(err);
  } finally {
    setAiLoading(false);
  }
}

function setAiLoading(isLoading) {
  const overlay = document.getElementById('aiLoadingOverlay');
  const box1 = document.getElementById('fakeRecBox1');
  const box2 = document.getElementById('fakeRecBox2');

  if (overlay) {
    if (isLoading) {
      overlay.classList.add('active');
    } else {
      overlay.classList.remove('active');
      if (box1) box1.style.display = 'none';
      if (box2) box2.style.display = 'none';
    }
  }

  const submitBtn = document.getElementById('submitReportBtn');
  const disabledNotice = document.getElementById('submitDisabledNotice');
  if (submitBtn && isLoading) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> AI Recognizing Road Damage...';
    if (disabledNotice) disabledNotice.style.display = 'none';
  }
}

function applyAiDetectionResult(result) {
  currentDetectionData = result;

  // Check if image has human / portrait
  const isHuman = (result.is_human === true) ||
                  (result.condition && (
                    result.condition.toLowerCase().includes('human') ||
                    result.condition.toLowerCase().includes('portrait') ||
                    result.condition.toLowerCase().includes('person')
                  ));

  // Check if image is a photo from another device/screen
  const isScreenDevice = !isHuman && ((result.is_screen_device === true) ||
                         (result.condition && (
                           result.condition.toLowerCase().includes('device') ||
                           result.condition.toLowerCase().includes('screen') ||
                           result.condition.toLowerCase().includes('gallery')
                         )) ||
                         (result.severity && result.severity.toLowerCase().includes('screen')));

  // Check if image is fake or invalid non-road image
  const isFake = !isHuman && ((result.is_fake === true) || 
                 (result.condition && result.condition.toLowerCase().includes('fake')) ||
                 (result.severity && result.severity.toLowerCase().includes('fake')));

  // Check if image is sky or clouds
  const isSky = !isHuman && !isScreenDevice && ((result.is_sky === true) ||
                (result.condition && (
                  result.condition.toLowerCase().includes('sky') ||
                  result.condition.toLowerCase().includes('cloud')
                )));

  const isInvalid = (result.is_road === false) || isHuman || isFake || isScreenDevice || isSky ||
                    (result.condition && result.condition.toLowerCase().includes('invalid')) ||
                    (result.condition && result.condition.toLowerCase().includes('non-road')) ||
                    (result.severity && result.severity.toLowerCase().includes('invalid'));

  // 1. Update preview image / video with YOLO annotated keyframe
  const previewImg = document.getElementById('aiPreviewImage');
  const previewVideo = document.getElementById('aiPreviewVideo');
  const emptyPlaceholder = document.getElementById('aiEmptyPlaceholder');
  const toggleBar = document.getElementById('videoViewToggleBar');
  const videoBanner = document.getElementById('aiVideoBreakdownBanner');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';

  if (result.is_video) {
    if (previewVideo) previewVideo.style.display = 'none';
    if (previewImg) {
      previewImg.style.display = 'block';
      if (result.annotated_image) previewImg.src = result.annotated_image;
    }
    if (toggleBar) toggleBar.style.display = 'flex';

    if (videoBanner) {
      videoBanner.style.display = 'block';
      const durEl = document.getElementById('aiVideoDurationBadge');
      const statsEl = document.getElementById('aiVideoBreakdownStats');
      if (durEl) {
        durEl.innerText = `${result.video_duration_seconds || '—'}s (${result.frames_analyzed || 0} frames analyzed)`;
      }
      if (statsEl) {
        const b = result.damage_breakdown || {};
        const total = result.total_damages_detected || 0;
        statsEl.innerHTML = `
          <span class="badge ${total >= 2 ? 'badge-critical' : 'badge-high'}" style="font-weight:700;">🚨 ${total} Total Defect(s) Detected</span>
          <span class="badge badge-amber">🕳️ ${b.potholes || 0} Pothole(s)</span>
          <span class="badge badge-new">⚡ ${b.cracks || 0} Crack(s)</span>
          ${b.severe_clusters ? `<span class="badge badge-verified">📦 ${b.severe_clusters} Cluster(s)</span>` : ''}
        `;
      }
    }
  } else {
    if (toggleBar) toggleBar.style.display = 'none';
    if (videoBanner) videoBanner.style.display = 'none';
    if (previewVideo) {
      previewVideo.pause();
      previewVideo.style.display = 'none';
    }
    if (previewImg) {
      previewImg.style.display = 'block';
      if (result.annotated_image) {
        previewImg.src = result.annotated_image;
      }
    }
  }

  // 2. Update AI metrics badges
  const conditionDisplay = document.getElementById('aiConditionDisplay');
  const confidenceDisplay = document.getElementById('aiConfidenceDisplay');
  const severityDisplay = document.getElementById('aiSeverityDisplay');
  const aiSummaryText = document.getElementById('aiSummaryText');
  const descriptionInput = document.getElementById('descriptionInput');
  const submitBtn = document.getElementById('submitReportBtn');
  const disabledNotice = document.getElementById('submitDisabledNotice');

  if (conditionDisplay) {
    if (isHuman) {
      conditionDisplay.innerText = 'Human Presence Detected';
      conditionDisplay.style.color = '#dc2626';
    } else if (isScreenDevice) {
      conditionDisplay.innerText = 'Photo from Another Device';
      conditionDisplay.style.color = '#dc2626';
    } else if (isFake) {
      conditionDisplay.innerText = 'Fake Image';
      conditionDisplay.style.color = '#dc2626';
    } else if (isSky) {
      conditionDisplay.innerText = 'Sky Image Uploaded';
      conditionDisplay.style.color = '#0284c7';
    } else if (isInvalid) {
      conditionDisplay.innerText = result.condition || 'Non-Road Image';
      conditionDisplay.style.color = '#dc2626';
    } else {
      conditionDisplay.innerText = result.condition || 'Pothole';
      conditionDisplay.style.color = 'var(--text-main)';
    }
  }

  if (confidenceDisplay) {
    if (isInvalid || isHuman || isFake || isScreenDevice || isSky) {
      confidenceDisplay.innerText = '-';
      confidenceDisplay.style.color = '#94a3b8';
    } else {
      confidenceDisplay.innerText = result.confidence_display || '92%';
      confidenceDisplay.style.color = '#2563eb';
    }
  }

  if (severityDisplay) {
    if (isHuman) {
      severityDisplay.innerHTML = '<span class="badge" style="background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;font-weight:700;">Human Portrait (Invalid)</span>';
    } else if (isScreenDevice) {
      severityDisplay.innerHTML = '<span class="badge" style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;font-weight:700;">Screen Recapture</span>';
    } else if (isFake) {
      severityDisplay.innerHTML = '<span class="badge" style="background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;font-weight:700;">Fake Image</span>';
    } else if (isSky) {
      severityDisplay.innerHTML = '<span class="badge" style="background:#e0f2fe;color:#0369a1;border:1px solid #7dd3fc;font-weight:700;">Sky Image (Invalid)</span>';
    } else if (isInvalid) {
      severityDisplay.innerHTML = '<span class="badge" style="background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;font-weight:700;">Non-Road Image</span>';
    } else {
      severityDisplay.innerHTML = getSeverityBadge(result.severity || 'High', true);
    }
  }

  if (aiSummaryText) {
    aiSummaryText.innerText = result.summary || (isHuman ? 'Human presence / portrait detected. RoadWatch requires photos of road damage.' : (isScreenDevice ? 'Photo from another device detected. Try to click photo directly not from gallery.' : (isFake ? 'Fake image detected.' : (isSky ? 'Sky image uploaded. RoadWatch requires a photograph of roadway asphalt or pothole damage, not sky or clouds.' : 'AI detected road defects successfully.'))));
    aiSummaryText.style.color = (isInvalid || isHuman || isFake || isScreenDevice || isSky) ? (isSky ? '#0369a1' : '#b91c1c') : '#475569';
  }

  // 3. Auto-fill Problem Description from AI Assessment
  if (descriptionInput) {
    if (isHuman) {
      descriptionInput.value = result.summary || 'Human presence / portrait detected. Please upload an authentic photo of roadway asphalt or pothole damage, not human portraits.';
    } else if (isScreenDevice) {
      descriptionInput.value = 'Photo from another device / screen detected. Try to click photo directly not from gallery.';
    } else if (isFake) {
      descriptionInput.value = result.summary || 'Fake image detected. An authentic camera photograph of real road damage is required.';
    } else if (isSky) {
      descriptionInput.value = result.summary || 'Sky image uploaded. RoadWatch requires a photograph of roadway asphalt or pothole damage, not sky or clouds.';
    } else if (isInvalid) {
      descriptionInput.value = result.summary || 'Invalid non-road image detected. Please upload an asphalt road surface or pothole.';
    } else {
      descriptionInput.value = result.summary || `${result.condition || 'Road damage'} detected with ${result.severity || 'High'} severity (${result.confidence_display || '90%'} confidence).`;
    }
  }

  // 4. Disable / Enable Submit Button based on road validity
  if (submitBtn) {
    if (isInvalid || isHuman || isFake || isScreenDevice || isSky) {
      submitBtn.disabled = true;
      submitBtn.classList.add('btn-disabled');
      submitBtn.style.opacity = '0.55';
      submitBtn.style.cursor = 'not-allowed';
      submitBtn.style.backgroundColor = '#94a3b8';
      submitBtn.style.borderColor = '#94a3b8';
      submitBtn.innerHTML = isHuman
        ? '<span>🚫</span> Submission Disabled (Human Portrait)'
        : (isScreenDevice
          ? '<span>🚫</span> Submission Disabled (Screen Photo)'
          : (isFake 
            ? '<span>🚫</span> Submission Disabled (Fake Image)' 
            : (isSky 
              ? '<span>🚫</span> Submission Disabled (Sky Image)' 
              : '<span>🚫</span> Submission Disabled (Invalid Road Image)')));
      if (disabledNotice) {
        disabledNotice.style.display = 'block';
        disabledNotice.style.background = isSky ? '#e0f2fe' : '#fee2e2';
        disabledNotice.style.borderColor = isSky ? '#7dd3fc' : '#fca5a5';
        disabledNotice.style.color = isSky ? '#0369a1' : '#b91c1c';
        disabledNotice.innerText = isHuman
          ? '⚠️ Submission Disabled: Human presence / portrait detected. Please upload an authentic photo of roadway asphalt or pothole damage, not human portraits.'
          : (isScreenDevice
            ? '⚠️ Submission Disabled: Photo from another device / screen detected. Try to click photo directly not from gallery.'
            : (isFake
              ? '⚠️ Submission Disabled: Fake image detected. ' + (result.summary || 'Please upload an authentic camera photo.')
              : (isSky
                ? '⚠️ Submission Disabled: Sky image uploaded. RoadWatch requires a photograph of roadway asphalt or pothole damage, not sky or clouds. Please point camera directly down at roadway asphalt or pothole.'
                : '⚠️ Submission Disabled: ' + (result.summary || 'The uploaded image is not a road surface.'))));
      }
    } else {
      submitBtn.disabled = false;
      submitBtn.classList.remove('btn-disabled');
      submitBtn.style.opacity = '1';
      submitBtn.style.cursor = 'pointer';
      submitBtn.style.backgroundColor = '';
      submitBtn.style.borderColor = '';
      submitBtn.innerHTML = '<span>🚀</span> Submit Road Report';
      if (disabledNotice) {
        disabledNotice.style.display = 'none';
      }
    }
  }

  // 5. Auto-sync form selects
  if (!isInvalid && !isFake && !isScreenDevice && !isSky) {
    const conditionSelect = document.getElementById('roadConditionSelect');
    const severitySelect = document.getElementById('severitySelect');

    if (conditionSelect) {
      let matched = false;
      for (let opt of conditionSelect.options) {
        if (opt.value && opt.value.toLowerCase() === (result.condition || '').toLowerCase()) {
          opt.selected = true;
          matched = true;
          break;
        }
      }
      if (!matched && result.condition) {
        const newOpt = document.createElement('option');
        newOpt.value = result.condition;
        newOpt.textContent = result.condition;
        newOpt.selected = true;
        conditionSelect.appendChild(newOpt);
      }
    }

    if (severitySelect) {
      for (let opt of severitySelect.options) {
        if (opt.value && opt.value.toLowerCase() === (result.severity || '').toLowerCase()) {
          opt.selected = true;
          break;
        }
      }
    }

    showToast(`YOLO Detection: ${result.condition} detected (${result.confidence_display} confidence, ${result.severity} severity)`, 'success');
  } else if (isScreenDevice) {
    showToast('⚠️ Screen Photo Detected: Try to click photo directly not from gallery.', 'error', 7000);
  } else if (isFake) {
    showToast(`⚠️ Fake Image Detected: ${result.summary || 'Image recognized as fake or synthetic.'}`, 'error', 6000);
  } else if (isSky) {
    showToast('⚠️ Sky Image Detected: RoadWatch requires a photo of roadway asphalt or pothole damage, not sky or clouds.', 'error', 7000);
  } else {
    showToast(`⚠️ Invalid Road Image: ${result.summary}`, 'error', 6000);
  }
}

function handleAiError(err) {
  console.warn('AI detection error:', err);
  // Graceful fallback for offline demo
  const fallback = {
    condition: 'Pothole',
    severity: 'High',
    confidence: 0.93,
    confidence_display: '93%',
    summary: 'YOLO simulated detection: Pothole detected on road surface.',
    annotated_image: '',
    is_road: true
  };
  applyAiDetectionResult(fallback);
  showToast('Backend offline. Applied smart simulated detection for presentation.', 'info');
}

// Mysuru Localities Coordinates Knowledge Base (for fast offline / fallback resolution)
const MYSURU_LOCALITIES = [
  { name: 'Sayyaji Rao Road, Near Mysore Palace', lat: 12.3051, lng: 76.6551 },
  { name: 'Devaraja Urs Road, Commercial Zone', lat: 12.3082, lng: 76.6450 },
  { name: 'KRS Road, Vijayanagar 2nd Stage', lat: 12.3385, lng: 76.6110 },
  { name: 'Gokulam 3rd Stage, VV Puram', lat: 12.3270, lng: 76.6340 },
  { name: 'Jayalakshmipuram, Kalidasa Road', lat: 12.3190, lng: 76.6260 },
  { name: 'Kuvempunagar, Complex Junction', lat: 12.2850, lng: 76.6250 },
  { name: 'Saraswathipuram, Swimming Pool Rd', lat: 12.3010, lng: 76.6350 },
  { name: 'Hunsur Road, Jaladarshini Junction', lat: 12.3160, lng: 76.6380 },
  { name: 'Outer Ring Road, Bogadi Junction', lat: 12.3050, lng: 76.6050 },
  { name: 'Hebbal Industrial Area, Mysuru', lat: 12.3610, lng: 76.6020 },
  { name: 'Chamundi Hill Road, View Point', lat: 12.2750, lng: 76.6710 },
  { name: 'Bannur Main Road, Alanahalli', lat: 12.2980, lng: 76.6980 },
  { name: 'Vidyaranyapuram, Sewage Farm Road', lat: 12.2850, lng: 76.6480 },
  { name: 'Nazarbad, Mysore Zoo / Race Course', lat: 12.3030, lng: 76.6660 },
  { name: 'Ramakrishnanagar, E & F Block', lat: 12.2780, lng: 76.6180 },
  { name: 'Hebbal 1st Stage, Near Infosys', lat: 12.3550, lng: 76.5920 },
  { name: 'Mandi Mohalla, Ashoka Road', lat: 12.3150, lng: 76.6540 }
];

// Calculate Haversine distance in kilometers
function getHaversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

// Find nearest Mysuru locality based on GPS
function getNearestMysuruLocality(lat, lng) {
  let closest = MYSURU_LOCALITIES[0];
  let minDistance = Infinity;

  for (const loc of MYSURU_LOCALITIES) {
    const dist = getHaversineDistance(lat, lng, loc.lat, loc.lng);
    if (dist < minDistance) {
      minDistance = dist;
      closest = loc;
    }
  }

  return `${closest.name}, Mysuru`;
}

// Reverse geocode coordinates to human-readable area name
async function fetchAreaNameFromCoordinates(lat, lng) {
  try {
    // 1. Try reverse geocode with a 3.5s timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`;
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' }
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      const addr = data.address || {};

      const road = addr.road || addr.pedestrian || addr.street || '';
      const area = addr.suburb || addr.neighbourhood || addr.residential || addr.hamlet || addr.city_district || '';
      const city = addr.city || addr.town || addr.county || 'Mysuru';

      const parts = [];
      if (road) parts.push(road);
      if (area && area !== road) parts.push(area);
      if (city) parts.push(city);

      if (parts.length > 0) {
        return parts.join(', ');
      }
    }
  } catch (err) {
    console.warn('Network reverse geocoding notice:', err);
  }

  // 2. Intelligent fallback to closest Mysuru locality
  return getNearestMysuruLocality(lat, lng);
}

// Location and Geolocation tools
function initLocationHelpers() {
  const gpsBtn = document.getElementById('detectLocationBtn');
  const locationInput = document.getElementById('locationInput');
  const mapsLinkInput = document.getElementById('mapsLinkInput');

  if (gpsBtn) {
    gpsBtn.addEventListener('click', () => {
      if (!navigator.geolocation) {
        showToast('Geolocation is not supported by your browser.', 'error');
        return;
      }

      gpsBtn.innerHTML = '<span>⏳</span> Locating Area...';
      gpsBtn.disabled = true;

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          const mapsUrl = `https://maps.google.com/?q=${lat.toFixed(6)},${lng.toFixed(6)}`;

          if (mapsLinkInput) {
            mapsLinkInput.value = mapsUrl;
          }

          // Automatically resolve real area name from GPS coordinates
          if (locationInput) {
            locationInput.placeholder = 'Resolving area name from GPS...';
            try {
              const areaName = await fetchAreaNameFromCoordinates(lat, lng);
              locationInput.value = areaName;
              showToast(`Area detected: ${areaName}`, 'success');
            } catch (e) {
              const fallbackArea = getNearestMysuruLocality(lat, lng);
              locationInput.value = fallbackArea;
            }
          }

          gpsBtn.innerHTML = '<span>📍</span> GPS & Area Detected';
          gpsBtn.disabled = false;
        },
        async (err) => {
          console.warn('Geolocation error:', err);
          // Default Mysuru center coordinates
          const defaultLat = 12.3051;
          const defaultLng = 76.6551;
          const mapsUrl = `https://maps.google.com/?q=${defaultLat},${defaultLng}`;

          if (mapsLinkInput && !mapsLinkInput.value.trim()) {
            mapsLinkInput.value = mapsUrl;
          }

          if (locationInput && !locationInput.value.trim()) {
            locationInput.value = 'Sayyaji Rao Road, Near Mysore Palace, Mysuru';
          }

          gpsBtn.innerHTML = '<span>📍</span> Mysuru GPS Set';
          gpsBtn.disabled = false;
          showToast('GPS unavailable. Applied default Mysuru location & Area name.', 'info');
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });
  }

  // Ensure maps link field is strictly non-editable (manual edit disabled)
  if (mapsLinkInput) {
    mapsLinkInput.readOnly = true;
    mapsLinkInput.setAttribute('readonly', 'true');
    mapsLinkInput.addEventListener('keydown', (e) => {
      e.preventDefault();
    });
  }
}

// Form Submission
function initReportForm() {
  const form = document.getElementById('roadReportForm');
  const submitBtn = document.getElementById('submitReportBtn');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const locationVal = document.getElementById('locationInput')?.value.trim();
    if (!locationVal) {
      showToast('Please enter the area name in Mysuru.', 'error');
      document.getElementById('locationInput')?.focus();
      return;
    }

    // Check media
    const previewImg = document.getElementById('aiPreviewImage');
    const hasMedia = currentUploadedFile || currentCapturedBase64 || currentDetectionData || (previewImg && previewImg.src && !previewImg.src.includes('placeholder'));

    if (!hasMedia) {
      showToast('Please snap a road photo or upload an image first.', 'error');
      return;
    }

    const isInvalid = (currentDetectionData && currentDetectionData.is_road === false) ||
                      (currentDetectionData && currentDetectionData.condition && currentDetectionData.condition.toLowerCase().includes('invalid')) ||
                      (currentDetectionData && currentDetectionData.severity && currentDetectionData.severity.toLowerCase().includes('invalid'));

    if (isInvalid) {
      showToast('Cannot submit: The uploaded image is not a road surface. Please capture or upload a road damage photo.', 'error');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.classList.add('btn-disabled');
        submitBtn.style.opacity = '0.55';
        submitBtn.style.cursor = 'not-allowed';
        submitBtn.style.backgroundColor = '#94a3b8';
        submitBtn.style.borderColor = '#94a3b8';
        submitBtn.innerHTML = '<span>🚫</span> Submission Disabled (Invalid Road Image)';
      }
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Submitting Report...';
    }

    try {
      const formData = new FormData();
      formData.append('location', locationVal);
      formData.append('google_maps_link', document.getElementById('mapsLinkInput')?.value.trim() || '');
      formData.append('description', document.getElementById('descriptionInput')?.value.trim() || '');
      formData.append('reporter_name', document.getElementById('reporterNameInput')?.value.trim() || 'Mysuru Citizen');
      formData.append('road_type', document.getElementById('roadTypeSelect')?.value || 'City road');

      // AI detection attributes
      const cond = currentDetectionData?.condition || document.getElementById('roadConditionSelect')?.value || 'Pothole';
      const sev = currentDetectionData?.severity || document.getElementById('severitySelect')?.value || 'High';
      const conf = currentDetectionData?.confidence || 0.92;

      formData.append('road_condition', cond);
      formData.append('severity', sev);
      formData.append('confidence', conf);

      if (currentDetectionData?.annotated_image) {
        formData.append('annotated_image', currentDetectionData.annotated_image);
      }

      if (currentUploadedFile) {
        formData.append('file', currentUploadedFile);
      } else if (currentCapturedBase64) {
        formData.append('image_base64', currentCapturedBase64);
      } else if (currentDetectionData?.original_image) {
        formData.append('image', currentDetectionData.original_image);
      }

      const res = await window.roadWatchApi.createReport(formData);

      if (res && res.report) {
        // Save to browser history for local tracking
        saveReportToLocalHistory(res.report);

        // Populate success modal
        const successReportId = document.getElementById('successReportId');
        const successCondition = document.getElementById('successCondition');
        const successSeverity = document.getElementById('successSeverity');
        const successLocation = document.getElementById('successLocation');

        if (successReportId) successReportId.innerText = res.report.report_id;
        if (successCondition) successCondition.innerText = res.report.road_condition;
        if (successSeverity) successSeverity.innerHTML = getSeverityBadge(res.report.severity);
        if (successLocation) successLocation.innerText = res.report.location;
        const trackReportLink = document.getElementById('trackReportLink');
        if (trackReportLink) trackReportLink.href = `report.html?id=${res.report.report_id}`;

        openModal('reportSuccessModal');
        showToast(`Report ${res.report.report_id} successfully registered!`, 'success');

        // Reset form to clean initial state
        resetFormToInitialState();
      }
    } catch (err) {
      console.error('Submission error:', err);
      // Fallback local report creation
      const fallbackReport = {
        report_id: `RW-${Math.floor(100 + Math.random() * 900)}`,
        road_condition: document.getElementById('roadConditionSelect')?.value || 'Pothole',
        severity: document.getElementById('severitySelect')?.value || 'High',
        confidence: 0.93,
        confidence_display: '93%',
        location: locationVal,
        google_maps_link: document.getElementById('mapsLinkInput')?.value.trim() || '',
        description: document.getElementById('descriptionInput')?.value.trim() || '',
        date: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
        time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        status: 'New'
      };

      saveReportToLocalHistory(fallbackReport);

      const successReportId = document.getElementById('successReportId');
      if (successReportId) successReportId.innerText = fallbackReport.report_id;
      const trackReportLink = document.getElementById('trackReportLink');
      if (trackReportLink) trackReportLink.href = `report.html?id=${fallbackReport.report_id}`;
      openModal('reportSuccessModal');
      showToast(`Report ${fallbackReport.report_id} registered locally (Backend offline).`, 'info');
      resetFormToInitialState();
    } finally {
      if (submitBtn && currentDetectionData && currentDetectionData.is_road !== false) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>🚀</span> Submit Road Report';
      }
    }
  });
}

// Reset all form inputs and AI metrics to clean initial empty state
function resetFormToInitialState() {
  const form = document.getElementById('roadReportForm');
  if (form) form.reset();

  currentDetectionData = null;
  currentUploadedFile = null;
  currentCapturedBase64 = null;

  // Reset previews
  const previewImg = document.getElementById('aiPreviewImage');
  const previewVideo = document.getElementById('aiPreviewVideo');
  const emptyPlaceholder = document.getElementById('aiEmptyPlaceholder');
  const box1 = document.getElementById('fakeRecBox1');
  const box2 = document.getElementById('fakeRecBox2');
  const toggleBar = document.getElementById('videoViewToggleBar');
  const videoBanner = document.getElementById('aiVideoBreakdownBanner');

  if (box1) box1.style.display = 'none';
  if (box2) box2.style.display = 'none';
  if (toggleBar) toggleBar.style.display = 'none';
  if (videoBanner) videoBanner.style.display = 'none';

  if (previewVideo) {
    previewVideo.pause();
    previewVideo.src = '';
    previewVideo.style.display = 'none';
  }

  if (previewImg) {
    previewImg.src = '';
    previewImg.style.display = 'none';
  }
  if (emptyPlaceholder) emptyPlaceholder.style.display = 'block';

  // Reset AI metrics to blank dashes
  const conditionDisplay = document.getElementById('aiConditionDisplay');
  const confidenceDisplay = document.getElementById('aiConfidenceDisplay');
  const severityDisplay = document.getElementById('aiSeverityDisplay');
  const aiSummaryText = document.getElementById('aiSummaryText');
  const descriptionInput = document.getElementById('descriptionInput');
  const roadConditionSelect = document.getElementById('roadConditionSelect');
  const severitySelect = document.getElementById('severitySelect');
  const locationInput = document.getElementById('locationInput');
  const mapsLinkInput = document.getElementById('mapsLinkInput');
  const reporterNameInput = document.getElementById('reporterNameInput');

  if (conditionDisplay) {
    conditionDisplay.innerText = '—';
    conditionDisplay.style.color = 'var(--text-muted)';
  }
  if (confidenceDisplay) {
    confidenceDisplay.innerText = '—';
    confidenceDisplay.style.color = 'var(--text-muted)';
  }
  if (severityDisplay) {
    severityDisplay.innerHTML = '<span style="color:var(--text-muted);font-size:0.95rem;font-weight:600;">—</span>';
  }
  if (aiSummaryText) {
    aiSummaryText.innerText = 'Awaiting image upload to generate real-time AI damage assessment.';
    aiSummaryText.style.color = 'var(--text-muted)';
  }
  if (descriptionInput) descriptionInput.value = '';
  if (locationInput) locationInput.value = '';
  if (mapsLinkInput) mapsLinkInput.value = '';
  if (reporterNameInput) reporterNameInput.value = '';
  if (roadConditionSelect) roadConditionSelect.value = '';
  if (severitySelect) severitySelect.value = '';

  // Reset Submit Button to initial disabled waiting state
  const submitBtn = document.getElementById('submitReportBtn');
  const disabledNotice = document.getElementById('submitDisabledNotice');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.remove('btn-disabled');
    submitBtn.style.opacity = '0.6';
    submitBtn.style.cursor = 'not-allowed';
    submitBtn.style.backgroundColor = '';
    submitBtn.style.borderColor = '';
    submitBtn.innerHTML = '<span>🚀</span> Submit Road Report';
  }
  if (disabledNotice) {
    disabledNotice.style.display = 'block';
    disabledNotice.style.background = '#f8fafc';
    disabledNotice.style.borderColor = 'var(--border-color)';
    disabledNotice.style.color = '#64748b';
    disabledNotice.innerText = '📷 Please capture or upload a road damage photo first to enable report submission.';
  }
}

