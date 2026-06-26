import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import HomePage from './pages/HomePage';
import WikiPage from './pages/WikiPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={
          <>
            <Header />
            <main className="pt-14">
              <HomePage />
            </main>
          </>
        } />
        <Route path="/wiki/:repoUrl" element={<WikiPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
