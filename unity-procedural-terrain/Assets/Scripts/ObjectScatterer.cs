using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Scatters prefabs (trees, rocks, ...) onto a TerrainGenerator, only within a chosen height band
/// and only on gentle slopes. Uses Poisson-disc-style spacing so objects never overlap.
/// Right-click the component header and choose "Scatter" to run it.
/// </summary>
[RequireComponent(typeof(TerrainGenerator))]
public class ObjectScatterer : MonoBehaviour
{
    [System.Serializable]
    public class Layer
    {
        public string name = "Trees";
        public GameObject[] prefabs;
        [Range(0f, 1f)] public float minHeight = 0.36f;
        [Range(0f, 1f)] public float maxHeight = 0.62f;
        [Range(0f, 90f)] public float maxSlope = 30f;
        public float minSpacing = 2.5f;
        public int attempts = 4000;
        public Vector2 scaleRange = new Vector2(0.8f, 1.3f);
        public bool alignToSlope = false;
    }

    public List<Layer> layers = new List<Layer> { new Layer() };
    public int seed = 7;
    public bool scatterOnPlay = true;

    const string ContainerName = "_Scattered";

    void Start()
    {
        if (scatterOnPlay && Application.isPlaying) Scatter();
    }

    [ContextMenu("Scatter")]
    public void Scatter()
    {
        var terrain = GetComponent<TerrainGenerator>();
        if (terrain.HeightMap == null) terrain.Generate();
        Clear();

        var container = new GameObject(ContainerName).transform;
        container.SetParent(transform, false);
        var rng = new System.Random(seed);
        var collider = GetComponent<MeshCollider>();
        float size = terrain.resolution * terrain.cellSize;
        int n = terrain.resolution + 1;
        var placed = new List<Vector3>();

        foreach (var layer in layers)
        {
            if (layer.prefabs == null || layer.prefabs.Length == 0) continue;
            int count = 0;
            for (int i = 0; i < layer.attempts; i++)
            {
                // random point in local space, then ray down onto the actual mesh
                float lx = (float)rng.NextDouble() * size - size / 2f;
                float lz = (float)rng.NextDouble() * size - size / 2f;
                Vector3 top = transform.TransformPoint(new Vector3(lx, terrain.heightMultiplier + 10f, lz));
                if (!collider.Raycast(new Ray(top, Vector3.down), out RaycastHit hit, terrain.heightMultiplier * 3f)) continue;

                // check height band using the normalized height map
                int gx = Mathf.Clamp(Mathf.RoundToInt((lx + size / 2f) / terrain.cellSize), 0, n - 1);
                int gz = Mathf.Clamp(Mathf.RoundToInt((lz + size / 2f) / terrain.cellSize), 0, n - 1);
                float h = terrain.HeightMap[gx, gz];
                if (h < layer.minHeight || h > layer.maxHeight) continue;
                if (Vector3.Angle(hit.normal, Vector3.up) > layer.maxSlope) continue;

                // spacing check against everything placed so far (all layers)
                bool tooClose = false;
                foreach (var p in placed)
                    if ((p - hit.point).sqrMagnitude < layer.minSpacing * layer.minSpacing) { tooClose = true; break; }
                if (tooClose) continue;

                var prefab = layer.prefabs[rng.Next(layer.prefabs.Length)];
                Quaternion rot = Quaternion.Euler(0f, (float)rng.NextDouble() * 360f, 0f);
                if (layer.alignToSlope) rot = Quaternion.FromToRotation(Vector3.up, hit.normal) * rot;
                var obj = Instantiate(prefab, hit.point, rot, container);
                float s = Mathf.Lerp(layer.scaleRange.x, layer.scaleRange.y, (float)rng.NextDouble());
                obj.transform.localScale *= s;
                placed.Add(hit.point);
                count++;
            }
            Debug.Log($"[ObjectScatterer] Placed {count} × {layer.name}");
        }
    }

    [ContextMenu("Clear")]
    public void Clear()
    {
        var old = transform.Find(ContainerName);
        if (!old) return;
        if (Application.isPlaying) Destroy(old.gameObject);
        else DestroyImmediate(old.gameObject);
    }
}
