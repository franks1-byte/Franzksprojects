using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Generates a colored low-poly island mesh from fractal noise.
/// Add to an empty GameObject. The MeshFilter, MeshRenderer and MeshCollider are added automatically.
/// Change any setting in the Inspector to see the island rebuild instantly, even outside Play mode.
/// Assign a material that uses vertex colors (see README), or the island will render white.
/// </summary>
[ExecuteAlways]
[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer), typeof(MeshCollider))]
public class TerrainGenerator : MonoBehaviour
{
    [System.Serializable]
    public struct Biome
    {
        public string name;
        [Range(0f, 1f)] public float maxHeight;  // biome applies up to this normalized height
        public Color color;
    }

    [Header("Size")]
    [Range(16, 250)] public int resolution = 160;
    public float cellSize = 1f;
    public float heightMultiplier = 28f;
    [Tooltip("Reshapes heights: flat beaches and plains, steep mountains.")]
    public AnimationCurve heightCurve = new AnimationCurve(
        new Keyframe(0f, 0f), new Keyframe(0.3f, 0.02f), new Keyframe(0.36f, 0.05f), new Keyframe(0.66f, 0.32f), new Keyframe(1f, 1f));

    [Header("Noise")]
    public int seed = 42;
    public float noiseScale = 45f;
    [Range(1, 8)] public int octaves = 5;
    [Range(0f, 1f)] public float persistence = 0.5f;
    [Range(1f, 4f)] public float lacunarity = 2f;
    public Vector2 offset;

    [Header("Island")]
    public bool island = true;
    [Tooltip("How strongly the edges are pushed under water. Lower = bigger island.")]
    [Range(0f, 1f)] public float falloffStrength = 0.65f;

    [Header("Look")]
    public bool flatShading = true;  // low-poly faceted style
    public Biome[] biomes =
    {
        new Biome { name = "Deep water", maxHeight = 0.22f, color = new Color(0.05f, 0.15f, 0.40f) },
        new Biome { name = "Shallows",   maxHeight = 0.30f, color = new Color(0.10f, 0.45f, 0.70f) },
        new Biome { name = "Sand",       maxHeight = 0.35f, color = new Color(0.90f, 0.85f, 0.55f) },
        new Biome { name = "Grass",      maxHeight = 0.50f, color = new Color(0.35f, 0.65f, 0.25f) },
        new Biome { name = "Forest",     maxHeight = 0.64f, color = new Color(0.18f, 0.42f, 0.18f) },
        new Biome { name = "Rock",       maxHeight = 0.80f, color = new Color(0.42f, 0.38f, 0.36f) },
        new Biome { name = "Snow",       maxHeight = 1.00f, color = new Color(0.95f, 0.95f, 1.00f) },
    };

    [Header("Animation")]
    [Tooltip("Scroll the noise over time for a 'flying over endless land' effect.")]
    public Vector2 scrollSpeed = Vector2.zero;

    public float[,] HeightMap { get; private set; }

    Mesh mesh;
    bool dirty = true;
    // Reused between rebuilds to avoid garbage-collector spikes when sliders are dragged.
    readonly List<Vector3> verts = new List<Vector3>();
    readonly List<Color> colors = new List<Color>();
    readonly List<int> tris = new List<int>();
    float half;

    void OnValidate() => dirty = true;  // any Inspector change marks the mesh for a rebuild

    void Update()
    {
        if (scrollSpeed != Vector2.zero && Application.isPlaying)
        {
            offset += scrollSpeed * Time.deltaTime;
            dirty = true;
        }
        if (dirty) Generate();
    }

    [ContextMenu("Randomize Seed")]
    public void RandomizeSeed()
    {
        seed = Random.Range(0, 100000);
        Generate();
    }

    [ContextMenu("Generate")]
    public void Generate()
    {
        dirty = false;
        int n = resolution + 1;  // vertices per side

        HeightMap = Noise.HeightMap(n, n, seed, noiseScale, octaves, persistence, lacunarity, offset);
        if (island)
        {
            var falloff = Noise.Falloff(n, n, 3f, 2.6f);
            for (int y = 0; y < n; y++)
            for (int x = 0; x < n; x++)
                HeightMap[x, y] = Mathf.Clamp01(HeightMap[x, y] - falloffStrength * falloff[x, y]);
        }

        BuildMesh(n);
    }

    void BuildMesh(int n)
    {
        if (mesh == null)
        {
            mesh = new Mesh { name = "Procedural Terrain", indexFormat = IndexFormat.UInt32 };  // allow > 65k vertices
            GetComponent<MeshFilter>().sharedMesh = mesh;
        }
        mesh.Clear();

        verts.Clear(); colors.Clear(); tris.Clear();
        half = resolution * cellSize / 2f;

        if (flatShading)
        {
            // Every triangle gets its own 3 vertices, so normals are per-face: the low-poly look.
            for (int y = 0; y < resolution; y++)
            for (int x = 0; x < resolution; x++)
            {
                AddTriangle(Pos(x, y), Pos(x, y + 1), Pos(x + 1, y + 1),
                            (HeightMap[x, y] + HeightMap[x, y + 1] + HeightMap[x + 1, y + 1]) / 3f);
                AddTriangle(Pos(x, y), Pos(x + 1, y + 1), Pos(x + 1, y),
                            (HeightMap[x, y] + HeightMap[x + 1, y + 1] + HeightMap[x + 1, y]) / 3f);
            }
        }
        else
        {
            // Shared vertices give smooth shading.
            for (int y = 0; y < n; y++)
            for (int x = 0; x < n; x++)
            {
                verts.Add(Pos(x, y));
                colors.Add(ColorFor(HeightMap[x, y]));
            }
            for (int y = 0; y < resolution; y++)
            for (int x = 0; x < resolution; x++)
            {
                int i = y * n + x;
                tris.AddRange(new[] { i, i + n, i + n + 1, i, i + n + 1, i + 1 });
            }
        }

        mesh.SetVertices(verts);
        mesh.SetColors(colors);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        GetComponent<MeshCollider>().sharedMesh = mesh;
    }

    /// <summary>World position of a grid vertex (centered on this object).</summary>
    Vector3 Pos(int x, int y) => new Vector3(x * cellSize - half, WorldHeight(HeightMap[x, y]), y * cellSize - half);

    void AddTriangle(Vector3 a, Vector3 b, Vector3 c, float h)
    {
        int start = verts.Count;
        verts.Add(a); verts.Add(b); verts.Add(c);
        Color col = ColorFor(h);
        colors.Add(col); colors.Add(col); colors.Add(col);
        tris.Add(start); tris.Add(start + 1); tris.Add(start + 2);
    }

    /// <summary>Water stays flat; land follows the height curve.</summary>
    public float WorldHeight(float h)
    {
        float water = biomes.Length > 1 ? biomes[1].maxHeight : 0.30f;
        return heightCurve.Evaluate(Mathf.Max(h, water)) * heightMultiplier;
    }

    Color ColorFor(float h)
    {
        foreach (var b in biomes)
            if (h <= b.maxHeight) return b.color;
        return biomes.Length > 0 ? biomes[biomes.Length - 1].color : Color.white;
    }
}
