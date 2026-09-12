# Character Rigs

Each character has an editable Blender source and a skinned GLB:

| Character | Blender Source | Web Asset |
| --- | --- | --- |
| Master | `npc_master.blend` | `npc_master.glb` |
| Apprentice | `npc_apprentice.blend` | `npc_apprentice.glb` |
| YQ | `npc_yq.blend` | `npc_yq.glb` |

The original `../npc_*.glb` files are unchanged. The page loads the copies here.

## Skeleton

Each rig contains 20 bones: a non-deforming root; pelvis, spine, chest, neck,
head; and clavicle, upper arm, forearm, hand, thigh, shin and foot on each side.
`.L` and `.R` refer to the character's left and right.

The bind pose is the original sculpted pose, not a T-pose. In Blender, select
the armature, enter Pose Mode and rotate the body bones. These are FK rigs,
without IK controls, facial controls or independently articulated fingers.
Textures are packed into the Blender files.

## Animation

Motion revision 3 uses grounded standing behavior instead of repeated steps.

| Character | Idle | Greet | Listen |
| --- | --- | --- | --- |
| Master | 16s: slow breath, weight shift and occasional side glance | 67 frames: lift head and acknowledge with a nod | 8s: quiet attention |
| Apprentice | 19s: relaxed knees, tired shoulder posture and lowered head | 82 frames: delayed attention, slight straightening and nod | 9s: head slightly raised |
| YQ | 17s: balanced stance, breath and occasional downward glance | 62 frames: nod and restrained empty-hand gesture | 8.5s: quiet attention |

Greeting durations use 24 fps. The loops start and end at matching poses.
Both ankle targets were held fixed in Blender while pelvis, knees and torso
adjusted. IK was baked into the existing FK skeleton; there is no runtime IK.
The page offsets idle phases so the characters do not move in unison.

- `Idle`: default looping behavior.
- `Greet`: a single acknowledgement, not a repeated talking or waving loop.
- `Listen`: a quieter loop while the selected character's dialog remains open.
- `RigCheck`: six-second diagnostic sequence for head, arms and both legs.
  This is a deformation test, not a production walk or hammering animation.

`../../character-motion.js` blends these states. Hover adds limited head/neck
attention after a short delay. Selection plays `Greet` then blends to `Listen`;
closing the dialog or selecting another object returns to `Idle`. Repeated
clicks during a greeting or cooldown do not restart it. Camera drags and
multi-touch gestures do not trigger selection. Root scale and rotation are
not animated as click feedback.

GLB skinning uses at most four weights per vertex. Blender's armature modifier
uses linear skinning to match Three.js. Do not apply the old name-based T-pose
correction to these assets.

## Limits

The supplied characters are single continuous meshes. Tools, hands, clothing
and some body contact surfaces are welded together. Skinning preserves this
geometry; it does not create hidden surfaces at those contacts.

The current idle uses the legs for small weight adjustments with planted foot
anchors; it is not a walk cycle. Animation blending and mixed skin weights
can still produce small contact deformation even with fixed bone anchors.
The mesh, UVs, rest bones and weights are unchanged from the first rigging pass.

Larger arm movement can stretch the bucket/boot and book/apron contacts; even
YQ's empty hand has a fused contact with the apron. The hammer and pickaxe also
contact the shoulders. Small gestures retain minor contact deformation.
Large swings, walking retargets, releasing props or opening the sculpted grips
require separating those regions, rebuilding hidden surfaces and testing new
weights. Do not treat `RigCheck` as approval for those motions.

The original triangles and embedded texture bytes are retained. Draco export
may split a few vertices at attribute seams and introduces small coordinate
quantization error. Source and export hashes are in `manifest.json`.
