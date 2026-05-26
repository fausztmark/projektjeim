#include "framework.h"
#include <vector>
#include <random>
#include <algorithm>

const char* vertSource = R"(
            #version 330
            layout(location = 0) in vec2 vertexPosition;
            uniform mat4 MVP;
            void main() {
                gl_Position = MVP * vec4(vertexPosition, 0, 1);
            }
        )";

const char* fragSource = R"(
            #version 330
            uniform vec3 color;
            out vec4 fragColor;
            void main() {
                fragColor = vec4(color, 1);
            }
        )";
const int winWidth = 600, winHeight = 600;
class Camera {
private:
    vec3 eye = vec3(0.0f, 0.0f, 2.0f);
    vec3 lookat = vec3(0.0f, 0.0f, 0.0f);
    vec3 up = vec3(0.0f, 1.0f, 0.0f);
    float fov = 45.0f * (float)M_PI / 180.0f;
    float aspect = 1.0f;
    float near = 0.1f;
    float far = 100.0f;
    float moveStep = 0.1f;
public:
    mat4 getVPMatrix() { return P() * V(); }
    void setZoom(float z) { eye.z = 2.0f / z; }
    mat4 V() { return lookAt(eye, lookat, up); }
    mat4 P() { return perspective(fov, aspect, near, far); }
    void move(float dx, float dy) {
        eye.x += dx;
        eye.y += dy;
        lookat.x += dx;
        lookat.y += dy;
    }
    vec3 screenToWorld(const vec3& screenPos) {
        float normalizedX = (screenPos.x / winWidth) * 2.0f - 1.0f;
        float normalizedY = 1.0f - (screenPos.y / winHeight) * 2.0f;
        float normalizedZ = screenPos.z * 2.0f - 1.0f;
        vec4 ndcPos = vec4(normalizedX, normalizedY, normalizedZ, 1.0f);
        mat4 invVP = inverse(P() * V());
        vec4 worldPos = invVP * ndcPos;
        worldPos /= worldPos.w;

        return vec3(worldPos);
    }
    vec3 getEye() { return eye; }
    void moveLeft() { move(-moveStep, 0.0f); }
    void moveRight() { move(moveStep, 0.0f); }
    void moveUp() { move(0.0f, moveStep); }
    void moveDown() { move(0.0f, -moveStep); }
}; 
class Triangle {
private:
    Geometry<vec2> a, b, c;
    Geometry<vec2> aEdges, bEdges, cEdges;

public:
    void createLShape(Geometry<vec2>& geom, Geometry<vec2>& edges, vec2 dir, float r, float w, vec2 start) {
        geom.Vtx().clear();
        edges.Vtx().clear();
        float cos120 = -0.5f;
        float sin120 = 0.8660254f; // sqrt(3)/2

        vec2 rot120 = vec2(
            dir.x * cos120 - dir.y * sin120,
            dir.x * sin120 + dir.y * cos120
        );
        vec2 rot60 = vec2(
            dir.x * -cos120 - dir.y * sin120,
            dir.x * sin120 + dir.y * -cos120
        );

        // Pontok az L-alakhoz
        vec2 p1 = start;
        vec2 p0 = p1 - dir * w;
        vec2 p2 = p1 + rot120 * (r - w);
        vec2 p3 = p0 + rot120 * (r - w);

        vec2 q0 = p3;
        vec2 q1 = q0 + dir * (r - 2*w);
        vec2 q2 = q1 + rot60 * w;
        vec2 q3 = p3 + rot120 * w;

        // Metszéspont (két L szár csúcsa találkozásánál)
        vec2 inner = intersect(p1, p2, q0, q1);

        // Kitöltõ háromszögek (két téglalap)
        geom.Vtx().push_back(p0); geom.Vtx().push_back(p1); geom.Vtx().push_back(p2);
        geom.Vtx().push_back(p0); geom.Vtx().push_back(p2); geom.Vtx().push_back(p3);
        geom.Vtx().push_back(q0); geom.Vtx().push_back(q1); geom.Vtx().push_back(q2);
        geom.Vtx().push_back(q0); geom.Vtx().push_back(q2); geom.Vtx().push_back(q3);
        geom.updateGPU();

        // Kontúrvonal (körülmegy az alakzat szélén)
        edges.Vtx().push_back(p0);
        edges.Vtx().push_back(p1);
        edges.Vtx().push_back(inner);
        edges.Vtx().push_back(q1);
        edges.Vtx().push_back(q2);
        edges.Vtx().push_back(q3);
        edges.Vtx().push_back(p0);
        edges.updateGPU();
    }

    vec2 intersect(vec2 a1, vec2 a2, vec2 b1, vec2 b2) {
        vec2 da = a2 - a1;
        vec2 db = b2 - b1;
        float det = da.x * db.y - da.y * db.x;
        if (fabs(det) < 1e-6f) return vec2(0);
        vec2 dp = b1 - a1;
        float t = (dp.x * db.y - dp.y * db.x) / det;
        return a1 + da * t;
    }

    Triangle(float r, float w) {
        float step = r - w;

        vec2 dir0 = vec2(cos(-M_PI / 3.0f), sin(-M_PI / 3.0f));
        vec2 dir1 = vec2(cos(-3.0f * M_PI / 3.0f), sin(-3.0f * M_PI / 3.0f));
        vec2 dir2 = vec2(cos(-5.0f * M_PI / 3.0f), sin(-5.0f * M_PI / 3.0f));

        createLShape(a, aEdges, dir0, r, w, vec2(-0.5f, -0.5f));
        vec2 base1 = aEdges.Vtx()[aEdges.Vtx().size() - 2];
        createLShape(b, bEdges, dir1, r, w, base1);
        vec2 base2 = bEdges.Vtx()[bEdges.Vtx().size() - 2];
        createLShape(c, cEdges, dir2, r, w, base2);
    }

    void draw(GPUProgram* program) {
        a.Draw(program, GL_TRIANGLES, vec3(0.4f, 0.4f, 1.0f));
        b.Draw(program, GL_TRIANGLES, vec3(0.2f, 0.2f, 1.0f));
        c.Draw(program, GL_TRIANGLES, vec3(0.0f, 0.0f, 1.0f));
        aEdges.Draw(program, GL_LINE_LOOP, vec3(1, 1, 1));
        bEdges.Draw(program, GL_LINE_LOOP, vec3(1, 1, 1));
        cEdges.Draw(program, GL_LINE_LOOP, vec3(1, 1, 1));
    }
};
class Ball {
private:
    Geometry<vec2> geom;
    float radius;
public:
    Ball(float r) : radius(r) {
        geom.Vtx().clear();
        vec2 pos = vec2(-0.515f, -0.385f);
        geom.Vtx().push_back(pos);
        for (int i = 0; i <= 30; i++) {
            float angle = i * 2 * M_PI / 30;
            geom.Vtx().push_back(pos + vec2(cos(angle), sin(angle)) * radius);
        }
        geom.updateGPU();
    }
    void setPosition(vec2 pos) {
        geom.Vtx().clear();
        geom.Vtx().push_back(pos);
        for (int i = 0; i <= 30; i++) {
            float angle = i * 2 * M_PI / 30;
            geom.Vtx().push_back(pos + vec2(cos(angle), sin(angle)) * radius);
        }
        geom.updateGPU();
    }

    void draw(GPUProgram* program) {
        geom.Draw(program, GL_TRIANGLE_FAN, vec3(1, 0, 0));
    }
	void animate(float dt) {
		static float angle = 0.0f;
		angle += dt * 2 * M_PI / 3;
		if (angle >= 2 * M_PI) angle -= 2 * M_PI;
		vec2 pos = vec2(cos(angle), sin(angle)) * 0.4f * 0.9f;
		setPosition(pos);
	}
};
class MyApp : public glApp {
private:
    GPUProgram* program;
    Triangle* triangle;
    Ball* ball;
    float t = 0;
public:
    MyApp() : glApp("Penrose Triangle") {}

    void onInitialization() override {
        glClearColor(0, 0, 0, 1);
        program = new GPUProgram(vertSource, fragSource);
        triangle = new Triangle(1.0f, 0.15f);
        ball = new Ball(0.03f);
    }

    void onDisplay() override {
        glClear(GL_COLOR_BUFFER_BIT);
        program->Use();
        mat4 MVP = mat4(1);
        program->setUniform(MVP, "MVP");
        triangle->draw(program);
        ball->draw(program);
    }
    void onTimeElapsed(float startTime, float endTime) {
        float dt = 0.01f;
        for (float t = startTime; t < endTime; t += dt) {
            float Dt = fmin(dt, endTime - t);
            ball->animate(Dt);
        }
        refreshScreen();
    }
}; MyApp app;