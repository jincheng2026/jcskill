export const APPROVED_PROFILE_NAMES = new Set([
  '1080p_native_overlay_h264_crf8',
  'source_size_native_overlay_h264_crf8',
  '1080p_native_overlay_h264_videotoolbox_45m',
]);

const roundEven = (value) => {
  const rounded = Math.round(Number(value));
  return rounded % 2 === 0 ? rounded : rounded + 1;
};

export function canonicalQualityProfile({sourceWidth, sourceHeight, requestedName}) {
  const width = Number(sourceWidth);
  const height = Number(sourceHeight);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new Error(`invalid source dimensions: ${sourceWidth}x${sourceHeight}`);
  }
  const upscale = width < 1080;
  const outputWidth = upscale ? 1080 : roundEven(width);
  const outputHeight = upscale ? roundEven((height / width) * outputWidth) : roundEven(height);
  const defaultName = upscale ? '1080p_native_overlay_h264_crf8' : 'source_size_native_overlay_h264_crf8';
  const name = requestedName || defaultName;
  if (!APPROVED_PROFILE_NAMES.has(name)) throw new Error(`unapproved quality profile: ${name}`);
  if (upscale && name !== '1080p_native_overlay_h264_crf8') {
    throw new Error(`sub-1080 sources must use 1080p_native_overlay_h264_crf8, got ${name}`);
  }
  if (!upscale && name === '1080p_native_overlay_h264_crf8') {
    throw new Error('1080p_native_overlay_h264_crf8 is only for sub-1080 sources');
  }
  const hardware = name === '1080p_native_overlay_h264_videotoolbox_45m';
  return {
    name,
    deliveryIntent: 'quality_master',
    upscale: {enabled: upscale, filter: upscale ? 'spline36' : null},
    output: {width: outputWidth, height: outputHeight},
    overlay: {
      renderScale: Number((outputWidth / width).toFixed(6)),
      width: outputWidth,
      height: outputHeight,
    },
    videoEncoding: hardware
      ? {
          codec: 'h264_videotoolbox',
          bitrate: '45M',
          profile: 'high',
          pixelFormat: 'yuv420p',
          colorSpace: 'bt709',
          colorTransfer: 'bt709',
          colorPrimaries: 'bt709',
          colorRange: 'tv',
        }
      : {
          codec: 'libx264',
          preset: 'slow',
          crf: 8,
          profile: 'high',
          pixelFormat: 'yuv420p',
          colorSpace: 'bt709',
          colorTransfer: 'bt709',
          colorPrimaries: 'bt709',
          colorRange: 'tv',
        },
  };
}

export function qualityProfileDifferences(actual, expected) {
  const fields = [
    'name',
    'deliveryIntent',
    'upscale.enabled',
    'upscale.filter',
    'output.width',
    'output.height',
    'overlay.renderScale',
    'overlay.width',
    'overlay.height',
    'videoEncoding.codec',
    'videoEncoding.preset',
    'videoEncoding.crf',
    'videoEncoding.bitrate',
    'videoEncoding.profile',
    'videoEncoding.pixelFormat',
    'videoEncoding.colorSpace',
    'videoEncoding.colorTransfer',
    'videoEncoding.colorPrimaries',
    'videoEncoding.colorRange',
  ];
  const read = (value, key) => key.split('.').reduce((current, part) => current?.[part], value);
  return fields
    .map((field) => ({field, actual: read(actual, field), expected: read(expected, field)}))
    .filter(({actual: left, expected: right}) => {
      if (typeof right === 'number') return !Number.isFinite(Number(left)) || Math.abs(Number(left) - right) > 0.000001;
      return (left ?? null) !== (right ?? null);
    });
}

export function assertCanonicalQuality(actual, sourceDimensions) {
  const expected = canonicalQualityProfile({
    sourceWidth: sourceDimensions.width,
    sourceHeight: sourceDimensions.height,
    requestedName: actual?.name,
  });
  const differences = qualityProfileDifferences(actual, expected);
  if (differences.length) {
    throw new Error(`quality profile differs from canonical contract: ${differences.map((item) => `${item.field}=${item.actual} expected ${item.expected}`).join('; ')}`);
  }
  return expected;
}
