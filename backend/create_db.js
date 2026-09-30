const mysql = require('mysql2/promise');

async function createDatabase() {
    try {
        const connection = await mysql.createConnection({
            host: 'localhost',
            user: 'root',
            password: ''
        });
        await connection.query('CREATE DATABASE IF NOT EXISTS cyclonexus_db;');
        console.log("Successfully created database 'cyclonexus_db'.");
        await connection.end();
    } catch (error) {
        console.error("Error creating database:", error);
    }
}

createDatabase();
