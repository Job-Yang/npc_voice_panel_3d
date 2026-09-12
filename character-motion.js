import * as THREE from 'three';

export class CharacterMotion {
  constructor(root, clips, phase = 0) {
    this.root = root;
    this.mixer = new THREE.AnimationMixer(root);
    this.actions = {};
    this.weights = {};
    this.state = 'Idle';
    this.responseCount = 0;
    this.nextResponseAt = 0;
    this.hoverTime = 0;
    this.lookYaw = 0;
    this.lookPitch = 0;
    this.neck = root.getObjectByName('neck');
    this.head = root.getObjectByName('head');
    this.vector = new THREE.Vector3();
    this.headPosition = new THREE.Vector3();
    this.rootQuaternion = new THREE.Quaternion();
    this.parentQuaternion = new THREE.Quaternion();
    this.turn = new THREE.Quaternion();
    this.attentionBones = [[this.neck, 0.3], [this.head, 0.7]]
      .filter(([bone]) => bone)
      .map(([bone, portion]) => ({ bone, portion, base: bone.quaternion.clone() }));
    for (const name of ['Idle', 'Greet', 'Listen']) {
      const clip = THREE.AnimationClip.findByName(clips, name);
      if (!clip) continue;
      const action = this.mixer.clipAction(clip);
      action.setEffectiveWeight(name === 'Idle' ? 1 : 0);
      if (name === 'Greet') {
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
      } else {
        action.play();
        action.time = phase % clip.duration;
      }
      this.actions[name] = action;
      this.weights[name] = name === 'Idle' ? 1 : 0;
    }
    this.mixer.update(0);
    this.attentionBones.forEach(({ bone, base }) => base.copy(bone.quaternion));
  }

  transition(name) {
    if (!this.actions[name]) name = 'Idle';
    if (name === this.state) return;
    this.fromWeights = { ...this.weights };
    this.blendElapsed = 0;
    this.blendDuration = name === 'Greet' ? 0.32 : 0.65;
    this.state = name;
  }

  respond(selected = false) {
    const action = this.actions.Greet;
    if (!action || this.state === 'Greet' || this.mixer.time < this.nextResponseAt) return false;
    action.reset().setEffectiveWeight(0).play();
    this.weights.Greet = 0;
    this.greetingSelected = selected;
    this.nextResponseAt = this.mixer.time + action.getClip().duration + 0.4;
    this.responseCount++;
    this.transition('Greet');
    return true;
  }

  update(delta, { selected, hovered, camera }) {
    if (this.state === 'Greet') {
      const action = this.actions.Greet;
      if ((this.greetingSelected && !selected) ||
          action.time + delta >= action.getClip().duration - 0.65) {
        this.transition(selected ? 'Listen' : 'Idle');
      }
    } else {
      this.transition(selected ? 'Listen' : 'Idle');
    }
    if (this.fromWeights) {
      this.blendElapsed += delta;
      const t = Math.min(1, this.blendElapsed / this.blendDuration);
      const ease = t * t * (3 - 2 * t);
      for (const [name, action] of Object.entries(this.actions)) {
        this.weights[name] = this.fromWeights[name] * (1 - ease) + (name === this.state ? ease : 0);
        action.setEffectiveWeight(this.weights[name]);
      }
      if (t === 1) this.fromWeights = null;
    }
    // PropertyMixer may skip unchanged tracks; remove last frame's gaze first.
    this.attentionBones.forEach(({ bone, base }) => bone.quaternion.copy(base));
    this.mixer.update(delta);
    this.attentionBones.forEach(({ bone, base }) => base.copy(bone.quaternion));
    this.hoverTime = hovered ? this.hoverTime + delta : 0;
    this.updateAttention(delta, selected || this.state === 'Greet' ? 1 : this.hoverTime > 0.18 ? 0.55 : 0, camera);
  }

  updateAttention(delta, attention, camera) {
    if (!this.head || !camera) return;
    this.root.updateWorldMatrix(true, true);
    this.head.getWorldPosition(this.headPosition);
    this.vector.copy(camera.position).sub(this.headPosition);
    this.root.getWorldQuaternion(this.rootQuaternion);
    this.vector.applyQuaternion(this.parentQuaternion.copy(this.rootQuaternion).invert());
    const yaw = THREE.MathUtils.clamp(Math.atan2(this.vector.x, this.vector.z), -0.34, 0.34) * attention;
    const pitch = THREE.MathUtils.clamp(
      -Math.atan2(this.vector.y, Math.hypot(this.vector.x, this.vector.z)), -0.09, 0.09,
    ) * attention;
    const alpha = 1 - Math.exp(-Math.min(delta, 0.25) * 4);
    this.lookYaw += (yaw - this.lookYaw) * alpha;
    this.lookPitch += (pitch - this.lookPitch) * alpha;
    for (const { bone, portion } of this.attentionBones) {
      // Convert world-space gaze deltas into each bone parent's coordinates.
      bone.parent.getWorldQuaternion(this.parentQuaternion).invert();
      this.vector.set(0, 1, 0).applyQuaternion(this.parentQuaternion);
      this.turn.setFromAxisAngle(this.vector, this.lookYaw * portion);
      bone.quaternion.premultiply(this.turn);
      this.vector.set(1, 0, 0).applyQuaternion(this.rootQuaternion).applyQuaternion(this.parentQuaternion);
      this.turn.setFromAxisAngle(this.vector, this.lookPitch * portion);
      bone.quaternion.premultiply(this.turn);
      bone.updateWorldMatrix(false, true);
    }
  }

  snapshot() {
    return {
      state: this.state,
      weights: { ...this.weights },
      responseCount: this.responseCount,
      lookYaw: this.lookYaw,
      lookPitch: this.lookPitch,
      times: Object.fromEntries(Object.entries(this.actions).map(([name, action]) => [name, action.time])),
    };
  }
}
