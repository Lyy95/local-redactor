export function isVisualFinding(finding, location) {
  return Boolean(
    location?.imageId
    || finding?.actionSet === "image"
    || finding?.category === "图片",
  );
}
