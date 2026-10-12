using UnityEngine;

/// <summary>
/// Fractal noise helpers. Layers several "octaves" of Perlin noise: each octave has higher
/// frequency (more detail) and lower amplitude (less influence), the way real landscapes have
/// big mountains made of smaller hills made of even smaller bumps.
/// </summary>
public static class Noise
{
    public static float[,] HeightMap(int width, int height, int seed, float scale,
                                     int octaves, float persistence, float lacunarity, Vector2 offset)
    {
        var map = new float[width, height];
        var prng = new System.Random(seed);
        var octaveOffsets = new Vector2[octaves];
        float amplitude = 1f;

        for (int i = 0; i < octaves; i++)
        {
            // Large random offsets so each octave samples a different region of the noise.
            octaveOffsets[i] = new Vector2(prng.Next(-100000, 100000) + offset.x, prng.Next(-100000, 100000) + offset.y);
        }

        scale = Mathf.Max(scale, 0.0001f);
        float halfW = width / 2f, halfH = height / 2f;
        float minV = float.MaxValue, maxV = float.MinValue;

        for (int y = 0; y < height; y++)
        for (int x = 0; x < width; x++)
        {
            amplitude = 1f;
            float frequency = 1f, value = 0f;
            for (int i = 0; i < octaves; i++)
            {
                float sx = (x - halfW) / scale * frequency + octaveOffsets[i].x;
                float sy = (y - halfH) / scale * frequency + octaveOffsets[i].y;
                value += (Mathf.PerlinNoise(sx, sy) * 2f - 1f) * amplitude;  // range -1..1
                amplitude *= persistence;
                frequency *= lacunarity;
            }
            map[x, y] = value;
            if (value < minV) minV = value;
            if (value > maxV) maxV = value;
        }

        // Stretch to the full 0..1 range so every biome (water to snow) appears.
        // (Summed octaves rarely reach their theoretical maximum, so dividing by it would squash everything toward 0.5.)
        for (int y = 0; y < height; y++)
        for (int x = 0; x < width; x++)
            map[x, y] = Mathf.InverseLerp(minV, maxV, map[x, y]);
        return map;
    }

    /// <summary>
    /// Island mask: 0 in the middle and 1 at the edges, with a smooth curve.
    /// Subtracting it from the height map pushes the borders under the sea.
    /// </summary>
    public static float[,] Falloff(int width, int height, float steepness = 3f, float shift = 2.2f)
    {
        var map = new float[width, height];
        for (int y = 0; y < height; y++)
        for (int x = 0; x < width; x++)
        {
            float nx = x / (float)(width - 1) * 2f - 1f;
            float ny = y / (float)(height - 1) * 2f - 1f;
            float v = Mathf.Max(Mathf.Abs(nx), Mathf.Abs(ny));
            float a = Mathf.Pow(v, steepness);
            map[x, y] = a / (a + Mathf.Pow(shift - shift * v, steepness));
        }
        return map;
    }
}
