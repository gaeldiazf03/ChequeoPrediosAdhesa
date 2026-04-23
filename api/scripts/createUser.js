#!/usr/bin/env node

import readline from 'readline'
import mysql from 'mysql2/promise.js'
import bcrypt from 'bcryptjs'
import * as dotenv from 'dotenv'

dotenv.config()

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
})

const question = (prompt) =>
  new Promise((resolve) => {
    rl.question(prompt, resolve)
  })

async function createUser() {
  let connection

  try {
    console.log('\n=== Creador de Usuarios - Chequeo Predios ===\n')

    // Obtener datos del usuario
    const username = await question('Usuario (username): ')
    const name = await question('Nombre completo: ')
    const email = await question('Email (opcional): ')
    const roleInput = await question('Rol (admin/manager/viewer) [viewer]: ')
    const passwordInput = await question('Contraseña: ')

    if (!username.trim() || !name.trim() || !passwordInput.trim()) {
      console.error('❌ Usuario, nombre y contraseña son requeridos.')
      rl.close()
      process.exit(1)
    }

    const role = ['admin', 'manager', 'viewer'].includes(roleInput) ? roleInput : 'viewer'
    const passwordHash = await bcrypt.hash(passwordInput, 10)

    // Conectar a BD
    connection = await mysql.createConnection({
      host: process.env.DB_HOST || 'localhost',
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || '',
      database: process.env.DB_NAME || 'chequeo_predios',
    })

    console.log('\n📝 Creando usuario...')

    // Insertar usuario
    const [result] = await connection.execute(
      'INSERT INTO users (username, password_hash, name, email, role, active) VALUES (?, ?, ?, ?, ?, 1)',
      [username, passwordHash, name, email || null, role],
    )

    console.log(`\n✅ Usuario creado exitosamente!`)
    console.log(`\n📋 Datos del usuario:`)
    console.log(`   Username: ${username}`)
    console.log(`   Nombre: ${name}`)
    console.log(`   Rol: ${role}`)
    console.log(`   Email: ${email || '(sin email)'}`)
    console.log(`\n💡 El usuario puede iniciar sesión inmediatamente.`)
  } catch (error) {
    if (error.code === 'ER_DUP_ENTRY') {
      console.error(`❌ El usuario '${error.sqlMessage}' ya existe.`)
    } else {
      console.error('❌ Error al crear usuario:', error.message)
    }
    process.exit(1)
  } finally {
    if (connection) {
      await connection.end()
    }
    rl.close()
  }
}

createUser()
