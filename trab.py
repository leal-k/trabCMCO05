from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from OpenGL.GLUT import glutBitmapCharacter, GLUT_BITMAP_HELVETICA_12
import math
import sys

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

BRANCO = (1.0, 1.0, 1.0)
PRETO = (0.0, 0.0, 0.0)
VERMELHO = (1.0, 0.0, 0.0)
VERDE = (0.0, 1.0, 0.0)
AZUL = (0.0, 0.0, 1.0)
AMARELO = (1.0, 1.0, 0.0)
CIANO = (0.0, 1.0, 1.0)
MAGENTA = (1.0, 0.0, 1.0)

ESTADOS = {
    "IDLE": 0,
    "APLICACAO": 1,
    "TRANSPORTE": 2,
    "REDE": 3,
    "ENLACE": 4,
    "FISICA": 5
}
estadoAtual = ESTADOS["IDLE"]
progressoAnimacao = 0.0
velocidadeAnimacao = 0.005
mensagem = "Oi!"

def init():
    glClearColor(*BRANCO, 1.0) #fundo da tela
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT) #sistema de coordenadas

def desenhaPC(x, y, scale=1.0, active=False): #active é pra mudar a cor do pc caso ele esteja ativo no momento da animação
    glPushMatrix()
    glTranslatef(x, y, 0)
    glScalef(scale, scale, 1)
    
    glColor3f(0.3, 0.3, 0.3)
    glBegin(GL_QUADS)
    glVertex2f(-30, -50)
    glVertex2f(30, -50)
    glVertex2f(30, 50)
    glVertex2f(-30, 50)
    glEnd()
    
    glColor3f(0.2, 0.2, 0.2)
    glBegin(GL_QUADS)
    glVertex2f(-60, 60)
    glVertex2f(60, 60)
    glVertex2f(60, 120)
    glVertex2f(-60, 120)
    glEnd()
    
    if active:
        glColor3f(0.8, 1.0, 0.8)
    else:
        glColor3f(0.1, 0.1, 0.1)
    glBegin(GL_QUADS)
    glVertex2f(-50, 70)
    glVertex2f(50, 70)
    glVertex2f(50, 110)
    glVertex2f(-50, 110)
    glEnd()
    
    glPopMatrix()

def desenhaMensagem(x, y, texto, nivelCor=None, rotation=0):
    glPushMatrix()
    glTranslatef(x, y, 0)
    glRotatef(rotation, 0, 0, 1)
    
    if nivelCor: #desenha as camadas em hexagonos, a cor é passada aqui
        raioNivel = 40
        for i, cor in enumerate(nivelCor):
            glColor3f(*cor)
            raio = raioNivel - i * 6
            glBegin(GL_POLYGON)
            for j in range(6):
                angulo = math.radians(60 * j)
                glVertex2f(math.cos(angulo) * raio, math.sin(angulo) * raio)
            glEnd()

    glColor3f(0, 0, 0)
    glRasterPos2f(-len(texto)*4, -5)
    for char in texto:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, ord(char))
    
    glPopMatrix()

def escreveTexto(x, y, texto):
    glColor3f(0, 0, 0)
    glRasterPos2f(x, y)
    for char in texto:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, ord(char))

def atualizaAnimacao():
    global estadoAtual, progressoAnimacao
    
    if estadoAtual != ESTADOS["IDLE"]: #avança até chegar em 100%, aí passa pra outra camada
        progressoAnimacao += velocidadeAnimacao
        if progressoAnimacao >= 1.0:
            progressoAnimacao = 0
            estadoAtual += 1
    
    glutPostRedisplay()

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    desenhaPC(150, 300, 1.0, estadoAtual >= ESTADOS["APLICACAO"])
    desenhaPC(650, 300, 1.0, estadoAtual >= ESTADOS["APLICACAO"])
    
    nivelCor = []
    
    if estadoAtual == ESTADOS["APLICACAO"]:
        nivelCor = [VERDE]
        desenhaMensagem(150, 200, mensagem, nivelCor)
        escreveTexto(90, 425, "Camada de Aplicacao: Mensagem original")
        
    elif estadoAtual == ESTADOS["TRANSPORTE"]:
        nivelCor = [AZUL, VERDE]
        desenhaMensagem(150, 200, mensagem, nivelCor)
        escreveTexto(90, 425, "Camada de Transporte: Cabecalho TCP/UDP")
        
    elif estadoAtual == ESTADOS["REDE"]:
        nivelCor = [AMARELO, AZUL, VERDE]
        desenhaMensagem(150, 200, mensagem, nivelCor)
        escreveTexto(90, 425, "Camada de Rede: Cabecalho IP")
        
    elif estadoAtual == ESTADOS["ENLACE"]:
        nivelCor = [VERMELHO, AMARELO, AZUL, VERDE]
        desenhaMensagem(150, 200, mensagem, nivelCor)
        escreveTexto(90, 425, "Camada de Enlace: Cabecalho Ethernet")
        
    elif estadoAtual == ESTADOS["FISICA"]:
        nivelCor = [MAGENTA, VERMELHO, AMARELO, AZUL, VERDE]
        desenhaMensagem(150, 200, mensagem, nivelCor)
        escreveTexto(90, 425, "Camada Fisica: Sinais eletricos")
        
    else: #idle
        escreveTexto(300, 500, "Pressione ESPACO para iniciar a animacao")
        escreveTexto(200, 450, "Demonstracao de encapsulamento de pacotes na rede")
    
    glutSwapBuffers()

def teclado(key, x, y):
    global estadoAtual, progressoAnimacao
    
    if key == b' ' and estadoAtual == ESTADOS["IDLE"]:
        estadoAtual = ESTADOS["APLICACAO"]
        progressoAnimacao = 0
    elif key == b'\x1b': #esc
        sys.exit(0)
    
    glutPostRedisplay()

def main():
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutCreateWindow(b"Encapsulamento de Pacotes na Rede")
    
    init()
    
    glutDisplayFunc(display)
    glutKeyboardFunc(teclado)
    glutIdleFunc(atualizaAnimacao)
    
    glutMainLoop()

if __name__ == "__main__":
    main()