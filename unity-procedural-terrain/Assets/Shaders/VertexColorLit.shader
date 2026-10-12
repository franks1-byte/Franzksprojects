// Simple lit shader that uses mesh vertex colors, for the Built-in Render Pipeline.
// For URP projects, see the README for a 2-minute Shader Graph alternative.
Shader "Custom/VertexColorLit"
{
    Properties
    {
        _Glossiness ("Smoothness", Range(0,1)) = 0.1
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows vertex:vert
        #pragma target 3.0

        half _Glossiness;

        struct Input { float4 vertColor; };

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.vertColor = v.color;
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            o.Albedo = IN.vertColor.rgb;
            o.Smoothness = _Glossiness;
            o.Metallic = 0;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
