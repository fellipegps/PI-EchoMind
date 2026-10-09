"""Contrato de retrieval do multilingual-e5-small na fronteira do encoder."""

from langchain_community.embeddings import FastEmbedEmbeddings


class E5FastEmbedEmbeddings(FastEmbedEmbeddings):
    """Recebe texto original; prefixa somente a copia enviada ao FastEmbed.

    Usa embed(), deliberadamente: query_embed()/passage_embed() podem aplicar
    instrucoes especificas do modelo em outras versoes do FastEmbed. Assim o
    adapter e o unico responsavel pelos prefixos, sem alterar o texto do PGVector.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            vector.tolist()
            for vector in self._model.embed(
                ["passage: " + text for text in texts],
                batch_size=self.batch_size,
                parallel=self.parallel,
            )
        ]

    def embed_query(self, text: str) -> list[float]:
        return next(
            self._model.embed(
                ["query: " + text],
                batch_size=self.batch_size,
                parallel=self.parallel,
            )
        ).tolist()
