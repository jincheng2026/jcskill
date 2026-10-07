import React from 'react';
import {Composition} from 'remotion';
import {TalkingHeadOverlay} from './TalkingHeadOverlay';
import {CANVAS} from './theme';
import type {OverlayProps} from './types';

export const Root: React.FC = () => (
  <Composition
    id="JCKouboOverlay"
    component={TalkingHeadOverlay}
    width={CANVAS.width}
    height={CANVAS.height}
    fps={CANVAS.fps}
    durationInFrames={CANVAS.durationInFrames}
    defaultProps={{manifest: {caseId: 'default'}}}
    calculateMetadata={({props}: {props: OverlayProps}) => {
      const video = props.manifest?.video || {};
      const output = props.manifest?.qualityProfile?.output || {};
      const sourceWidth = Number(video.width || CANVAS.width);
      const renderScale = Number(output.width || sourceWidth) / sourceWidth;
      return {
        width: sourceWidth,
        height: Number(video.height || CANVAS.height),
        fps: Number(video.fps || CANVAS.fps),
        durationInFrames: Number(video.frameCount || CANVAS.durationInFrames),
        props: {...props, renderScale},
      };
    }}
  />
);
