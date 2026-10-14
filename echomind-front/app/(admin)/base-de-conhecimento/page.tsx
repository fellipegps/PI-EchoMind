"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BookOpen, FileText } from "lucide-react";
import { FaqTab } from "./components/faq-tab";
import { DocumentTab } from "./components/document-tab";
import { PageHeader } from "@/components/page-header";
import { PageContainer } from "@/components/page-container";

export default function KnowledgeBasePage() {
  return (
    <PageContainer variant="standard">
      <PageHeader title="Base de Conhecimento" description="Gerencie as FAQs e os documentos usados pelo chatbot." />

      <Tabs defaultValue="faqs" className="w-full space-y-6">
        <TabsList aria-label="Áreas da base de conhecimento" className="w-full p-1 group-data-[orientation=horizontal]/tabs:h-auto sm:w-fit">
          <TabsTrigger value="faqs" className="min-h-11 gap-2 px-4 text-sm font-medium text-muted-foreground">
            <BookOpen aria-hidden="true" className="h-4 w-4" /> FAQs
          </TabsTrigger>
          <TabsTrigger value="documents" className="min-h-11 gap-2 px-4 text-sm font-medium text-muted-foreground">
            <FileText aria-hidden="true" className="h-4 w-4" /> Documentos
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
