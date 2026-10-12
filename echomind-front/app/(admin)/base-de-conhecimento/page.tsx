"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BookOpen, FileText } from "lucide-react";
import { FaqTab } from "./components/faq-tab";
import { DocumentTab } from "./components/document-tab";
import { PageHeader } from "@/components/page-header";
import { PageContainer } from "@/components/page-container";

export default function KnowledgeBasePage() {
  return (
    <PageContainer variant="wide">
      <PageHeader title="Base de Conhecimento" description="Gerencie as FAQs e os documentos usados pelo chatbot." />

      <Tabs defaultValue="faqs" className="w-full space-y-6">
        <TabsList className="bg-muted/50 p-1">
          <TabsTrigger value="faqs" className="gap-2 px-4 py-2 text-sm font-medium transition-all">
            <BookOpen className="h-4 w-4" /> FAQs
          </TabsTrigger>
          <TabsTrigger value="documents" className="gap-2 px-4 py-2 text-sm font-medium transition-all">
            <FileText className="h-4 w-4" /> Documentos
          </TabsTrigger>
        </TabsList>

        <TabsContent value="faqs" className="mt-0 outline-none">
          <FaqTab />
        </TabsContent>

        <TabsContent value="documents" className="mt-0 outline-none">
          <DocumentTab />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
