import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

/* Serveur de l'application : sert le front (Vite en développement, dist/ en production).
 * Aucun appel à un modèle externe : les analyses viennent de notre modèle NLP
 * (src/data/donnees-modele.json) et l'assistant Watchy est un agent à règles. */

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const { createServer } = await import('vite');
    const vite = await createServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (_req, res) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`WatchMyBusiness : http://localhost:${PORT}`);
  });
}

startServer();
