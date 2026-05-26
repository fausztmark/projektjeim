#include "framework.h" // A keretrendszer deklarációi
#include <glad/glad.h>
#define _USE_MATH_DEFINES // M_PI
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <vector>
#include <string>
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
using namespace glm;


class MyApp : public glApp {
	float red, green, blue, alpha; // színcsatornák
public:
	MyApp() : glApp("Grafika") {} // Megfogócsík szöveg
	void setRandomColor() { // véletlen szín
		red = (float)rand() / RAND_MAX;
		green = (float)rand() / RAND_MAX;
		blue = (float)rand() / RAND_MAX;
		alpha = 1.0f;
	}
	void onInitialization() { setRandomColor(); } // véletlen szín
	void onDisplay() {
		glClearColor(red, green, blue, alpha); // háttér szín
		glClear(GL_COLOR_BUFFER_BIT); // rasztertár törlés
	}
	void onKeyboard(int key) {
		setRandomColor(); // véletlen szín
		refreshScreen(); // onDisplay esemény
	}
} app;

template<class T> class Geometry {
protected:
	unsigned int vao, vbo; // GPU
	vector<T> vtx; // CPU
public:
	Geometry() {
		glGenVertexArrays(1, &vao); glBindVertexArray(vao);
		glGenBuffers(1, &vbo); glBindBuffer(GL_ARRAY_BUFFER, vbo);
	}
	virtual void updateGPU() { // CPU -> GPU
		glBindVertexArray(vao);
		glBindBuffer(GL_ARRAY_BUFFER, vbo);
		int nBytes = vtx.size() * sizeof(T);
		glBufferData(GL_ARRAY_BUFFER, nBytes, &vtx[0], GL_DYNAMIC_DRAW);
		int nf = min((int)(sizeof(T) / sizeof(float)), 4);
		glEnableVertexAttribArray(0);
		glVertexAttribPointer(0, nf, GL_FLOAT, GL_FALSE, 0, NULL);
	}
	void Bind() { glBindVertexArray(vao); }
	vector<T>& Vtx() { return vtx; }
	void Draw(GPUProgram* gpuProgram, int type, vec3 color) {
		if (vtx.size() > 0) {
			gpuProgram->setUniform(color, "color");
			glBindVertexArray(vao);
			glDrawArrays(type, 0, (int)vtx.size());
		}
	}
	virtual ~Geometry() {
		glDeleteBuffers(1, &vbo); glDeleteVertexArrays(1, &vao);
	}
};

const char* vertexSource = R"(
 #version 330
 layout(location = 0) in vec2 cP; // 0. bemeneti regiszter
 void main() { gl_Position = vec4(cP.x, cP.y, 0, 1); }
)";
void main() { gl_Position = vec4(cP.x, cP.y, 0, 1); }